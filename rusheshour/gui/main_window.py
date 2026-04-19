"""
Fenêtre principale RushesHour GUI.

Layout :
  ┌─────────────┬──────────────────────────────────┐
  │  FilePanel  │  PlayerWidget                    │
  │  (gauche)   │  TimelineWidget                  │
  │             │  Barre d'actions + infos          │
  └─────────────┴──────────────────────────────────┘

Mode de lancement : Option A — `python rusheshour_gui.py [dossier]`
"""

import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QInputDialog, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

from rusheshour             import __version__
from rusheshour.core.session  import Session
from rusheshour.core.scanner  import collect_videos, find_orphan_temps
from rusheshour.core.probe    import get_video_info, check_errors, is_already_mp4, format_duration
from rusheshour.core.actions  import finalize

from rusheshour.gui.player_widget   import PlayerWidget
from rusheshour.gui.timeline_widget import TimelineWidget
from rusheshour.gui.file_panel      import FilePanel
from rusheshour.gui.dialogs         import (
    RepairDialog, ConvertDialog, ExportDialog, DeleteConfirmDialog,
    OrphanCleanupDialog,
)


_DARK = """
QMainWindow, QWidget { background: #1e1e1e; color: #ddd; }
QPushButton {
    background: #2d2d2d; color: #ddd; border: 1px solid #444;
    padding: 4px 10px; border-radius: 3px;
}
QPushButton:hover   { background: #383838; }
QPushButton:pressed { background: #1a1a1a; }
QPushButton:disabled { color: #555; border-color: #333; }
QMenuBar { background: #252525; color: #ddd; }
QMenuBar::item:selected { background: #3a3a3a; }
QMenu { background: #252525; color: #ddd; border: 1px solid #444; }
QMenu::item:selected { background: #3a3a3a; }
QStatusBar { background: #252525; color: #aaa; font-size: 11px; }
QSplitter::handle { background: #333; }
"""


class _FileInfoWorker(QThread):
    """Récupère les métadonnées et détecte les erreurs hors du thread GUI."""

    ready = pyqtSignal(int, dict, list)   # (index, info, errors)

    def __init__(self, index: int, filepath: Path, opt_repair: bool) -> None:
        super().__init__()
        self._index      = index
        self._filepath   = filepath
        self._opt_repair = opt_repair

    def run(self) -> None:
        info   = get_video_info(self._filepath)
        errors = check_errors(self._filepath) if self._opt_repair else []
        self.ready.emit(self._index, info, errors)


class MainWindow(QMainWindow):
    def __init__(self, session: Session, parent=None) -> None:
        super().__init__(parent)
        self._session      = session
        self._videos:       list[Path]              = []
        self._current:      int                     = -1
        self._errors:       list[str]               = []
        self._current_info: dict                    = {}
        self._info_worker:  _FileInfoWorker | None  = None
        self._fullscreen:   bool                    = False
        self._mark_in:      float | None            = None
        self._mark_out:     float | None            = None

        self.setWindowTitle(f"RushesHour v{__version__}")
        self.setMinimumSize(1050, 650)
        self.setStyleSheet(_DARK)

        self._build_ui()
        self._build_menu()
        self._build_shortcuts()

        if session.root.is_dir() and session.root != Path("."):
            self._load_folder(session.root)

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self._splitter)

        self._file_panel = FilePanel()
        self._splitter.addWidget(self._file_panel)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        self._player   = PlayerWidget()
        self._timeline = TimelineWidget()

        rl.addWidget(self._player,   stretch=1)
        rl.addWidget(self._timeline)

        self._action_bar = self._build_action_bar()
        self._info_bar   = self._build_info_bar()
        rl.addWidget(self._action_bar)
        rl.addWidget(self._info_bar)

        self._splitter.addWidget(right)
        self._splitter.setSizes([250, 800])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        self._file_panel.file_selected.connect(self._on_file_selected_by_panel)
        self._player.position_changed.connect(self._timeline.set_position)
        self._player.duration_changed.connect(self._timeline.set_duration)
        self._player.pause_changed.connect(self._on_pause_changed)
        self._timeline.seek_requested.connect(self._player.seek)
        self._timeline.selection_changed.connect(self._on_selection_changed)

        self.statusBar().showMessage("Ouvrez un dossier via Fichier → Ouvrir")

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background:#252525; border-top:1px solid #333;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)

        def btn(label: str) -> QPushButton:
            b = QPushButton(label)
            b.setEnabled(False)
            layout.addWidget(b)
            return b

        self._btn_next    = btn("✓ Suivant [0]")
        self._btn_skip    = btn("→ Ne rien faire [1]")
        self._btn_rename  = btn("✏ Renommer [2]")
        self._btn_move    = btn("📂 Déplacer [3]")
        self._btn_delete  = btn("🗑 Supprimer [5]")
        self._btn_convert = btn("⚙ Convertir MP4 [6]")
        self._btn_repair  = btn("🔧 Réparer")
        self._btn_replay  = btn("▶ Rejouer [7]")
        self._btn_export  = btn("✂ Exporter clip [E]")

        layout.addStretch()

        self._btn_next.clicked.connect(self._act_next)
        self._btn_skip.clicked.connect(self._act_skip)
        self._btn_rename.clicked.connect(self._act_rename)
        self._btn_move.clicked.connect(self._act_move)
        self._btn_delete.clicked.connect(self._act_delete)
        self._btn_convert.clicked.connect(self._act_convert)
        self._btn_repair.clicked.connect(self._act_repair)
        self._btn_replay.clicked.connect(self._act_replay)
        self._btn_export.clicked.connect(self._act_export)

        return bar

    def _build_info_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background:#1a1a1a; border-top:1px solid #2a2a2a;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 3, 8, 3)

        self._lbl_file      = QLabel("—")
        self._lbl_index     = QLabel("")
        self._lbl_dest      = QLabel("")
        self._lbl_info      = QLabel("")
        self._lbl_selection = QLabel("")

        for lbl in (self._lbl_file, self._lbl_index, self._lbl_dest,
                    self._lbl_info, self._lbl_selection):
            lbl.setStyleSheet("color:#999; font-size:11px;")

        self._lbl_selection.setStyleSheet("color:#64b5f6; font-size:11px;")

        layout.addWidget(self._lbl_file,      stretch=1)
        layout.addWidget(self._lbl_index)
        layout.addWidget(self._lbl_info)
        layout.addWidget(self._lbl_selection)
        layout.addWidget(self._lbl_dest)

        return bar

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # Fichier
        m_file = mb.addMenu("&Fichier")
        a_open = m_file.addAction("Ouvrir un dossier…")
        a_open.setShortcut("Ctrl+O")
        a_open.triggered.connect(self._open_folder_dialog)
        m_file.addSeparator()
        a_quit = m_file.addAction("Quitter")
        a_quit.setShortcut("Ctrl+Q")
        a_quit.triggered.connect(self.close)

        # Options
        m_opts = mb.addMenu("&Options")

        self._act_opt_repair = m_opts.addAction("Réparation automatique")
        self._act_opt_repair.setCheckable(True)
        self._act_opt_repair.setChecked(self._session.opt_repair)
        self._act_opt_repair.triggered.connect(
            lambda c: setattr(self._session, "opt_repair", c)
        )

        self._act_opt_convert = m_opts.addAction("Proposition de conversion MP4")
        self._act_opt_convert.setCheckable(True)
        self._act_opt_convert.setChecked(self._session.opt_convert)
        self._act_opt_convert.triggered.connect(self._on_opt_convert_changed)

        m_opts.addSeparator()
        a_dest = m_opts.addAction("Définir la destination…")
        a_dest.triggered.connect(self._set_destination_dialog)

        # Aide
        m_help = mb.addMenu("&Aide")
        m_help.addAction("À propos").triggered.connect(self._show_about)

    def _build_shortcuts(self) -> None:
        bindings = {
            "0":      self._act_next,
            "1":      self._act_skip,
            "2":      self._act_rename,
            "3":      self._act_move,
            "5":      self._act_delete,
            "6":      self._act_convert,
            "7":      self._act_replay,
            "E":      self._act_export,
            "Space":  self._player.pause_toggle,
            "F":      self._toggle_fullscreen,
            "Escape": self._exit_fullscreen,
        }
        for key, slot in bindings.items():
            QShortcut(QKeySequence(key), self, slot)

    # ------------------------------------------------------------------
    # Chargement dossier / fichier
    # ------------------------------------------------------------------

    def _load_folder(self, root: Path) -> None:
        self._session.root = root
        extra = [self._session.output_dir] if self._session.output_dir else None
        orphans = find_orphan_temps(root, extra)
        if orphans:
            OrphanCleanupDialog(orphans, self).exec()
        self._videos = collect_videos(root, exclude_dir=self._session.output_dir)
        self._file_panel.set_files(self._videos)
        if self._videos:
            self._load_file(0)
            self.statusBar().showMessage(f"{len(self._videos)} vidéo(s) — {root}")
        else:
            self.statusBar().showMessage(f"Aucune vidéo dans : {root}")

    def _load_file(self, index: int) -> None:
        if not (0 <= index < len(self._videos)):
            return

        self._cancel_info_worker()

        self._current      = index
        self._errors       = []
        self._current_info = {}
        filepath           = self._videos[index]

        self._mark_in  = None
        self._mark_out = None
        self._file_panel.set_current(index)
        self._timeline.reset()
        self._player.load(filepath)
        self._set_actions_enabled(True)
        self._btn_export.setEnabled(False)
        self._btn_repair.setStyleSheet("")
        self._lbl_selection.setText("")
        self._btn_convert.setVisible(False)

        self._lbl_file.setText(filepath.name)
        self._lbl_index.setText(f"[{index + 1}/{len(self._videos)}]")
        self._lbl_info.setText("Analyse…")
        dest = str(self._session.output_dir) if self._session.output_dir else "destination : non définie"
        self._lbl_dest.setText(dest)

        worker = _FileInfoWorker(index, filepath, self._session.opt_repair)
        worker.ready.connect(self._on_file_info)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self._info_worker = worker

    def _cancel_info_worker(self) -> None:
        if self._info_worker is not None:
            try:
                self._info_worker.ready.disconnect(self._on_file_info)
            except RuntimeError:
                pass
            self._info_worker.wait()
            self._info_worker = None

    def _on_file_info(self, index: int, info: dict, errors: list[str]) -> None:
        if index != self._current:
            return

        self._current_info = info
        self._info_worker  = None

        filepath = self._videos[index]
        self._lbl_file.setText(filepath.name)
        self._lbl_index.setText(f"[{index + 1}/{len(self._videos)}]")

        if "error" not in info:
            dur   = format_duration(info.get("duration_s", 0.0))
            size  = info.get("size_mb", "?")
            codec = info.get("video_codec", "?")
            res   = info.get("resolution", "")
            self._lbl_info.setText(f"{codec}  {res}  {dur}  {size} Mo")
        else:
            self._lbl_info.setText(f"⚠ {info['error']}")

        if errors:
            self._errors = errors
            self._btn_repair.setStyleSheet("background:#b71c1c; color:white;")
            self._file_panel.mark_status(index, "error")
            self.statusBar().showMessage(
                f"⚠ {len(errors)} erreur(s) détectée(s) — cliquez Réparer"
            )

        self._refresh_action_visibility()

    def _refresh_action_visibility(self) -> None:
        mp4 = is_already_mp4(self._current_info)
        self._btn_convert.setVisible(self._session.opt_convert and not mp4)

    def _update_dest_label(self) -> None:
        dest = str(self._session.output_dir) if self._session.output_dir else "destination : non définie"
        self._lbl_dest.setText(dest)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for btn in (
            self._btn_next, self._btn_skip, self._btn_rename,
            self._btn_move, self._btn_delete, self._btn_convert,
            self._btn_repair, self._btn_replay, self._btn_export,
        ):
            btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Slots signaux
    # ------------------------------------------------------------------

    def _on_file_selected_by_panel(self, path: Path) -> None:
        try:
            idx = self._videos.index(path)
        except ValueError:
            return
        if idx != self._current:
            self._player.stop()
            self._load_file(idx)

    def _on_pause_changed(self, paused: bool) -> None:
        icon = "▶" if paused else "⏸"
        self.statusBar().showMessage(
            f"{icon}  {self._videos[self._current].name}"
            if 0 <= self._current < len(self._videos) else ""
        )

    def _on_opt_convert_changed(self, checked: bool) -> None:
        self._session.opt_convert = checked
        self._refresh_action_visibility()

    # ------------------------------------------------------------------
    # Actions fichier
    # ------------------------------------------------------------------

    def _act_next(self) -> None:
        if self._current < 0:
            return

        if (self._session.opt_convert
                and self._current_info
                and "error" not in self._current_info
                and not is_already_mp4(self._current_info)):
            r = QMessageBox.question(
                self, "Convertir en MP4 ?",
                f"« {self._videos[self._current].name} » n'est pas en MP4/H.264.\n"
                "Convertir avant de passer au suivant ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if r == QMessageBox.StandardButton.Yes:
                current  = self._current
                filepath = self._videos[current]
                self._player.stop()
                dlg = ConvertDialog(filepath, self._session.output_dir, self)
                dlg.exec()
                if current != self._current:
                    return
                if dlg.result_path == filepath:
                    # conversion annulée ou échouée — rester sur le fichier
                    self._load_file(current)
                    return
                self._videos[current] = dlg.result_path
                self._file_panel.update_path(current, dlg.result_path)
                self._file_panel.mark_status(current, "done")
                self._go_next()
                return

        filepath = self._videos[self._current]
        new_path = self._gui_finalize(filepath)
        if new_path is None:
            return
        self._videos[self._current] = new_path
        self._file_panel.update_path(self._current, new_path)
        self._file_panel.mark_status(self._current, "done")
        self._go_next()

    def _act_skip(self) -> None:
        if self._current < 0:
            return
        self._file_panel.mark_status(self._current, "done")
        self._go_next()

    def _act_rename(self) -> None:
        if self._current < 0:
            return
        filepath = self._videos[self._current]
        name, ok = QInputDialog.getText(
            self, "Renommer", "Nouveau nom (avec extension) :", text=filepath.name
        )
        if not ok or not name or name == filepath.name:
            return
        new_path = filepath.parent / name
        if new_path.exists():
            QMessageBox.warning(self, "Conflit", f"'{name}' existe déjà.")
            return
        filepath.rename(new_path)
        self._videos[self._current] = new_path
        self._file_panel.update_path(self._current, new_path)

    def _act_move(self) -> None:
        if self._current < 0:
            return
        filepath = self._videos[self._current]
        dest = self._pick_directory("Choisir le dossier de destination", str(filepath.parent))
        if not dest:
            return
        dest_dir = Path(dest)
        new_path = dest_dir / filepath.name
        if new_path.exists():
            r = QMessageBox.question(
                self, "Conflit", f"'{filepath.name}' existe déjà. Écraser ?"
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        shutil.move(str(filepath), str(new_path))
        self._videos[self._current] = new_path
        self._file_panel.update_path(self._current, new_path)

    def _act_delete(self) -> None:
        if self._current < 0:
            return
        filepath = self._videos[self._current]
        if DeleteConfirmDialog.confirm(filepath, self):
            filepath.unlink()
            self._file_panel.mark_status(self._current, "done")
            self._go_next()

    def _act_convert(self) -> None:
        if self._current < 0:
            return
        current  = self._current   # snapshot avant exec()
        filepath = self._videos[current]
        self._player.stop()
        dlg = ConvertDialog(filepath, self._session.output_dir, self)
        dlg.exec()
        if current != self._current:
            return   # l'utilisateur a navigué pendant le dialogue
        if dlg.result_path != filepath:
            self._videos[current] = dlg.result_path
            self._file_panel.update_path(current, dlg.result_path)
            self._file_panel.mark_status(current, "done")
            self._load_file(current)

    def _act_repair(self) -> None:
        if self._current < 0:
            return
        current  = self._current   # snapshot avant exec()
        filepath = self._videos[current]
        errors   = list(self._errors)
        self._player.stop()
        dlg = RepairDialog(filepath, errors, self)
        dlg.exec()
        if current != self._current:
            return   # l'utilisateur a navigué pendant le dialogue
        if dlg.result_path != filepath:
            self._videos[current] = dlg.result_path
            self._file_panel.update_path(current, dlg.result_path)
        self._load_file(current)

    def _act_replay(self) -> None:
        if 0 <= self._current < len(self._videos):
            self._player.load(self._videos[self._current])

    def _on_selection_changed(self, mark_in, mark_out) -> None:
        self._mark_in  = mark_in
        self._mark_out = mark_out
        valid = mark_in is not None and mark_out is not None and mark_out > mark_in
        self._btn_export.setEnabled(valid)
        if valid:
            clip_dur   = mark_out - mark_in
            dur_str    = format_duration(clip_dur)
            total_dur  = self._current_info.get("duration_s", 0.0)
            total_size = self._current_info.get("size_mb", 0.0)
            if total_dur > 0 and total_size > 0:
                est_mb  = round(total_size * clip_dur / total_dur, 1)
                size_str = f"~{est_mb} Mo"
            else:
                size_str = ""
            parts = [f"✂  {format_duration(mark_in)} → {format_duration(mark_out)}", dur_str]
            if size_str:
                parts.append(size_str)
            self._lbl_selection.setText("  |  ".join(parts))
        else:
            self._lbl_selection.setText("")

    def _act_export(self) -> None:
        if self._current < 0:
            return
        if self._mark_in is None or self._mark_out is None:
            return
        if self._mark_out <= self._mark_in:
            return
        filepath = self._videos[self._current]
        self._player.pause()
        dlg = ExportDialog(filepath, self._mark_in, self._mark_out, self._session.output_dir, self)
        dlg.exec()

    def _gui_finalize(self, filepath: Path) -> Path | None:
        """
        Déplace filepath vers output_dir avec gestion de collision Qt.
        Retourne le chemin final, ou None si l'utilisateur refuse l'écrasement.
        """
        if self._session.output_dir is None or not filepath.exists():
            return filepath
        try:
            filepath.relative_to(self._session.output_dir)
            return filepath  # déjà dans la destination
        except ValueError:
            pass
        dest = self._session.output_dir / filepath.name
        if dest.exists():
            r = QMessageBox.question(
                self, "Conflit de nom",
                f"« {filepath.name} » existe déjà dans la destination.\nÉcraser ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return None
        shutil.move(str(filepath), str(dest))
        return dest

    def _go_next(self) -> None:
        self._player.stop()
        nxt = self._current + 1
        if nxt < len(self._videos):
            self._load_file(nxt)
        else:
            self._set_actions_enabled(False)
            self._timeline.reset()
            self.statusBar().showMessage("✓ Toutes les vidéos ont été traitées.")

    # ------------------------------------------------------------------
    # Dialogues menu
    # ------------------------------------------------------------------

    def _open_folder_dialog(self) -> None:
        folder = self._pick_directory("Ouvrir un dossier de rushes")
        if folder:
            self._load_folder(Path(folder))

    def _set_destination_dialog(self) -> None:
        current = str(self._session.output_dir) if self._session.output_dir else ""
        folder = self._pick_directory("Choisir le dossier de destination", current)
        if folder:
            dest = Path(folder)
            dest.mkdir(parents=True, exist_ok=True)
            self._session.output_dir = dest
            self._update_dest_label()
            self.statusBar().showMessage(f"Destination : {dest}")

    def _pick_directory(self, title: str, start: str = "") -> str:
        """Sélecteur de dossier via processus externe (évite crash Qt XCB + OpenGL)."""
        import subprocess
        start = start or str(Path.home())
        # kdialog (KDE) — processus séparé, aucune interaction avec le contexte OpenGL
        if shutil.which("kdialog"):
            r = subprocess.run(
                ["kdialog", "--getexistingdirectory", start, "--title", title],
                capture_output=True, text=True,
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        # zenity (GNOME / fallback)
        if shutil.which("zenity"):
            r = subprocess.run(
                ["zenity", "--file-selection", "--directory",
                 f"--filename={start}/", f"--title={title}"],
                capture_output=True, text=True,
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        # macOS / Windows : QFileDialog ne souffre pas du conflit XCB+OpenGL
        import sys as _sys
        if _sys.platform != "linux":
            return QFileDialog.getExistingDirectory(
                self, title, start, QFileDialog.Option.ShowDirsOnly,
            )
        # Linux sans kdialog ni zenity : tkinter subprocess (stdlib, process isolé)
        try:
            import subprocess as _sp
            r = _sp.run(
                [_sys.executable, "-c",
                 "import tkinter; from tkinter import filedialog; "
                 "root=tkinter.Tk(); root.withdraw(); "
                 f"r=filedialog.askdirectory(initialdir={start!r}, title={title!r}); "
                 "print(r if r else '', end='')"],
                capture_output=True, text=True, timeout=300,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        # ultime recours : dialog Qt (peut crasher sur XWayland+mpv, dernier filet)
        return QFileDialog.getExistingDirectory(
            self, title, start,
            QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly,
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "À propos de RushesHour",
            f"<b>RushesHour v{__version__}</b><br>"
            "Outil de tri interactif de rush vidéo<br><br>"
            "Dépendances : mpv · ffmpeg · PyQt6<br>"
            "Licence : GPLv3<br>"
            "<a href='https://github.com/zobrak/RushesHour'>github.com/zobrak/RushesHour</a>",
        )

    # ------------------------------------------------------------------
    # Plein écran
    # ------------------------------------------------------------------

    def _toggle_fullscreen(self) -> None:
        if self._fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self) -> None:
        if self._fullscreen:
            return
        self._fullscreen = True
        self._file_panel.hide()
        self._action_bar.hide()
        self._info_bar.hide()
        self._timeline.hide()
        self.menuBar().hide()
        self.statusBar().hide()
        self.showFullScreen()

    def _exit_fullscreen(self) -> None:
        if not self._fullscreen:
            return
        self._fullscreen = False
        self.showNormal()
        self._file_panel.show()
        self._action_bar.show()
        self._info_bar.show()
        self._timeline.show()
        self.menuBar().show()
        self.statusBar().show()

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-clic sur la fenêtre principale → bascule plein écran."""
        self._toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._cancel_info_worker()
        self._player.shutdown()
        super().closeEvent(event)
