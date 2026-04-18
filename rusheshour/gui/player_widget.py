from pathlib import Path

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import pyqtSignal, Qt


# Empêche __del__ → terminate() d'être appelé depuis closeEvent().
# os._exit() dans launch_gui() tue le processus et toutes les ressources mpv.
_mpv_graveyard: list = []


class PlayerWidget(QWidget):
    """
    Lecteur vidéo embarqué via libmpv.

    Tous les observers mpv émettent via pyqtSignal — thread-safe.
    Si libmpv est absent, affiche un message d'erreur sans planter.

    Note Wayland : QT_QPA_PLATFORM=xcb doit être défini AVANT d'importer Qt.
    """

    position_changed = pyqtSignal(float)
    duration_changed = pyqtSignal(float)
    pause_changed    = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000;")

        # WA_NativeWindow requis pour obtenir un winId() stable avant show()
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)

        self._player = None
        self._mpv_available = False
        self._placeholder: QLabel | None = None

    # ------------------------------------------------------------------
    # Initialisation mpv (différée à show() pour winId() valide)
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._player is None and not self._mpv_available:
            self._try_init_player()

    def _try_init_player(self) -> None:
        try:
            import mpv
            self._player = mpv.MPV(
                wid=str(int(self.winId())),
                idle="yes",
                osc=True,
                input_vo_keyboard=True,
                input_default_bindings=False,  # pas de raccourcis mpv (q ne tue pas le contexte)
                log_handler=lambda *_: None,
                loglevel="no",
            )
            self._player.observe_property("time-pos", self._on_time_pos)
            self._player.observe_property("duration",  self._on_duration)
            self._player.observe_property("pause",     self._on_pause)
            self._mpv_available = True
        except Exception as exc:
            self._show_placeholder(f"mpv indisponible : {exc}")

    def _show_placeholder(self, msg: str) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(msg)
        lbl.setStyleSheet("color: #888; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        self._placeholder = lbl

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
        """
        Libère le PlayerWidget sans bloquer sur terminate().

        terminate() → _mpv_terminate_destroy() peut se retrouver en deadlock
        avec le thread d'événements python-mpv si appelé depuis closeEvent().
        On déplace la référence dans _mpv_graveyard pour empêcher __del__
        de déclencher terminate() ; os._exit() dans launch_gui() tue le
        processus entier sans attendre les threads mpv résiduels.
        """
        if self._player:
            _mpv_graveyard.append(self._player)  # empêche __del__ → terminate()
            self._player = None
            self._mpv_available = False

    @property
    def is_paused(self) -> bool:
        if self._player:
            return bool(self._player.pause)
        return True

    @property
    def mpv_available(self) -> bool:
        return self._mpv_available
