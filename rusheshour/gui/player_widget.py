"""
Widget lecteur mpv via l'API render OpenGL (QOpenGLWidget + MpvRenderContext).

On abandonne l'approche wid= (X11 window ID) qui crée une fenêtre flottante
sur certaines configurations Wayland/XWayland. L'API render rend directement
dans le framebuffer Qt — fenêtre proprement ancrée dans l'UI, fullscreen natif.

Dépendances runtime : python-mpv >= 0.5, libGL.so.1, mesa ou tout driver OpenGL 3.3+
"""
import ctypes
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QCoreApplication
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import pyqtSignal

# Empêche __del__ → terminate() depuis closeEvent() (risque de deadlock).
# os._exit() dans launch_gui() tue le processus entier.
_mpv_graveyard: list = []

# -- résolution des adresses de fonctions OpenGL (Linux/XWayland) -----------

_glXGetProcAddressARB = None

def _init_proc_addr() -> None:
    global _glXGetProcAddressARB
    if sys.platform != "linux":
        return
    for libname in ("libGL.so.1", "libGL.so", "libEGL.so.1", "libEGL.so"):
        try:
            lib = ctypes.CDLL(libname)
            fn = lib.glXGetProcAddressARB
            fn.restype = ctypes.c_void_p
            fn.argtypes = [ctypes.c_char_p]
            _glXGetProcAddressARB = fn
            return
        except (OSError, AttributeError):
            continue

_init_proc_addr()


# MpvRenderParam attend un CFunctionType, pas une fonction Python ordinaire.
_GetProcAddressFn = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)

def _get_proc_address_impl(_ctx, name: bytes) -> int:
    if _glXGetProcAddressARB is not None:
        return _glXGetProcAddressARB(name) or 0
    return 0

_get_proc_address = _GetProcAddressFn(_get_proc_address_impl)


# -- événement Qt thread-safe pour les callbacks mpv -------------------------

_MPV_UPDATE_EVENT = QEvent.Type(QEvent.registerEventType())


class PlayerWidget(QOpenGLWidget):
    """
    Lecteur vidéo embarqué — mpv rend dans le framebuffer Qt via l'API render.

    Thread-safety : les callbacks mpv (thread interne) postent un QEvent ;
    Qt le traite dans le thread principal → update() → paintGL().
    """

    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)
    pause_changed    = pyqtSignal(bool)

    def __init__(self, parent: QOpenGLWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setStyleSheet("background-color: #000;")

        self._player:      object | None = None
        self._render_ctx:  object | None = None
        self._mpv_available = False

    # ------------------------------------------------------------------
    # Initialisation OpenGL (appelée par Qt au premier show)
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:
        try:
            import mpv
        except ModuleNotFoundError:
            self._show_dep_error(
                "python-mpv non installé",
                "pip install python-mpv",
                "sudo apt install libmpv2",
            )
            return
        except OSError as exc:
            self._show_dep_error(
                "libmpv introuvable (bibliothèque C manquante)",
                "sudo apt install libmpv2",
                str(exc),
            )
            return

        try:
            self._player = mpv.MPV(
                vo="libmpv",
                idle="yes",
                osc=True,
                input_default_bindings=False,
                log_handler=lambda *_: None,
                loglevel="no",
            )
            self._player.observe_property("time-pos", self._on_time_pos)
            self._player.observe_property("duration",  self._on_duration)
            self._player.observe_property("pause",     self._on_pause)

            self._render_ctx = mpv.MpvRenderContext(
                self._player, "opengl",
                opengl_init_params={"get_proc_address": _get_proc_address},
            )
            self._render_ctx.update_cb = self._on_mpv_update
            self._mpv_available = True

        except Exception as exc:
            self._show_dep_error("Erreur d'initialisation mpv", str(exc))

    def _show_dep_error(self, title: str, *hints: str) -> None:
        from PyQt6.QtWidgets import QVBoxLayout, QLabel
        print(f"[PlayerWidget] {title}", file=sys.stderr)
        for h in hints:
            print(f"  → {h}", file=sys.stderr)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title = QLabel(f"⚠ {title}")
        lbl_title.setStyleSheet("color:#f44336; font-size:13px; font-weight:bold;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)
        for hint in hints:
            lbl = QLabel(hint)
            lbl.setStyleSheet("color:#888; font-size:11px; font-family:monospace;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)


    # ------------------------------------------------------------------
    # Pipeline de rendu Qt/OpenGL
    # ------------------------------------------------------------------

    def paintGL(self) -> None:
        if self._render_ctx is None:
            return
        fbo = self.defaultFramebufferObject()
        try:
            self._render_ctx.render(
                flip_y=True,
                opengl_fbo={"fbo": fbo, "w": self.width(), "h": self.height()},
            )
        except Exception:
            pass

    def resizeGL(self, w: int, h: int) -> None:
        if self._render_ctx:
            self._render_ctx.update()
            self.update()

    def event(self, ev: QEvent) -> bool:
        if ev.type() == _MPV_UPDATE_EVENT:
            self.update()
            return True
        return super().event(ev)

    # ------------------------------------------------------------------
    # Callback mpv → thread-safe via QEvent (pas d'appel Qt direct ici)
    # ------------------------------------------------------------------

    def _on_mpv_update(self) -> None:
        QCoreApplication.postEvent(self, QEvent(_MPV_UPDATE_EVENT))

    # ------------------------------------------------------------------
    # Observers mpv (thread mpv → signal Qt)
    # ------------------------------------------------------------------

    def _on_time_pos(self, _name: str, value) -> None:
        if value is not None:
            self.position_changed.emit(float(value))

    def _on_duration(self, _name: str, value) -> None:
        if value is not None:
            self.duration_changed.emit(float(value))

    def _on_pause(self, _name: str, value) -> None:
        if value is not None:
            self.pause_changed.emit(bool(value))

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def load(self, path: Path) -> None:
        if self._player:
            self._player.play(str(path))

    def play(self) -> None:
        if self._player:
            self._player.pause = False

    def pause_toggle(self) -> None:
        if self._player:
            self._player.pause = not self._player.pause

    def seek(self, pos: float) -> None:
        if self._player:
            try:
                self._player.seek(pos, "absolute")
            except Exception:
                pass

    def stop(self) -> None:
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass

    def shutdown(self) -> None:
        """Déplace les objets mpv dans le cimetière — évite __del__ → terminate()."""
        if self._render_ctx:
            _mpv_graveyard.append(self._render_ctx)
            self._render_ctx = None
        if self._player:
            _mpv_graveyard.append(self._player)
            self._player = None
            self._mpv_available = False

    @property
    def is_paused(self) -> bool:
        return bool(self._player.pause) if self._player else True

    @property
    def mpv_available(self) -> bool:
        return self._mpv_available
