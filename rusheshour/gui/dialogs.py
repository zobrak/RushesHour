"""
Dialogues GUI : réparation, conversion, confirmation suppression.

RepairWorker / ConvertWorker héritent de QThread et émettent des signaux
Qt — jamais de mise à jour de widget directe depuis le thread de travail.
"""

import re
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox,
)
from PyQt6.QtCore import QThread, pyqtSignal


# =============================================================================
# Workers (QThread)
# =============================================================================

class RepairWorker(QThread):
    """Exécute action_repair() dans un thread dédié."""

    log_line = pyqtSignal(str)
    finished = pyqtSignal(Path)
    failed   = pyqtSignal(str)

    def __init__(self, filepath: Path, errors: list[str]) -> None:
        super().__init__()
        self._filepath = filepath
        self._errors   = errors

    def run(self) -> None:
        import io, contextlib
        from rusheshour.core.repair import action_repair

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                result = action_repair(self._filepath, self._errors)
            for line in buf.getvalue().splitlines():
                if line.strip():
                    self.log_line.emit(line)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class ConvertWorker(QThread):
    """
    Lance ffmpeg en sous-processus et parse la progression via stderr.

    Parse les lignes du type :
      frame=...  fps=...  time=HH:MM:SS.ss  bitrate=...
    """

    progress_updated = pyqtSignal(int)   # 0-100
    log_line         = pyqtSignal(str)
    finished         = pyqtSignal(Path)
    failed           = pyqtSignal(str)

    _TIME_RE = re.compile(r"time=(\d+):(\d+):([\d.]+)")

    def __init__(self, filepath: Path, output_dir: Path | None) -> None:
        super().__init__()
        self._filepath   = filepath
        self._output_dir = output_dir

    def run(self) -> None:
        from rusheshour.core.convert import FFMPEG_ENCODE_FLAGS
        from rusheshour.core.probe   import get_video_info

        filepath   = self._filepath
        output_dir = self._output_dir

        if output_dir is not None:
            output_path = output_dir / filepath.with_suffix(".mp4").name
        else:
            output_path = filepath.with_suffix(".mp4")

        use_temp  = (output_path.resolve() == filepath.resolve())
        work_path = filepath.with_suffix(".tmp_converting.mp4") if use_temp else output_path

        info     = get_video_info(filepath)
        duration = info.get("duration_s", 0.0)

        cmd = ["ffmpeg", "-i", str(filepath)] + FFMPEG_ENCODE_FLAGS + ["-y", str(work_path)]

        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, errors="replace")

            assert proc.stderr is not None
            for line in proc.stderr:
                line = line.rstrip()
                m = self._TIME_RE.search(line)
                if m and duration > 0:
                    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    elapsed = h * 3600 + mn * 60 + s
                    pct = min(99, int(elapsed / duration * 100))
                    self.progress_updated.emit(pct)

            proc.wait()

            if proc.returncode != 0:
                if work_path.exists():
                    work_path.unlink()
                self.failed.emit("Conversion échouée (code ffmpeg ≠ 0)")
                return

            if filepath.exists():
                filepath.unlink()

            if use_temp:
                work_path.rename(output_path)

            self.progress_updated.emit(100)
            self.finished.emit(output_path)

        except Exception as exc:
            self.failed.emit(str(exc))


# =============================================================================
# Dialogues
# =============================================================================

class RepairDialog(QDialog):
    """Dialogue de réparation avec log et barre de progression indéterminée."""

    def __init__(self, filepath: Path, errors: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Réparation")
        self.setMinimumSize(520, 320)
        self.result_path: Path = filepath

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>Réparation de :</b> {filepath.name}"))

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indéterminé pendant le travail
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        self._log.setStyleSheet("background:#111; color:#ccc; font-family:monospace; font-size:11px;")
        layout.addWidget(self._log)

        self._btn = QPushButton("Fermer")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self.accept)
        layout.addWidget(self._btn)

        self._worker = RepairWorker(filepath, errors)
        self._worker.log_line.connect(self._log.append)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, result: Path) -> None:
        self.result_path = result
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._log.append(f"\n✓ Réparation terminée → {result.name}")
        self._btn.setEnabled(True)

    def _on_failed(self, msg: str) -> None:
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._log.append(f"\n✗ Erreur : {msg}")
        self._btn.setEnabled(True)


class ConvertDialog(QDialog):
    """Dialogue de conversion MP4 avec barre de progression réelle."""

    def __init__(self, filepath: Path, output_dir: Path | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conversion MP4")
        self.setMinimumWidth(420)
        self.result_path: Path = filepath

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>Conversion :</b> {filepath.name}"))
        layout.addWidget(QLabel("Encodage H.264 / AAC — CRF 23, preset medium"))

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._lbl = QLabel("En cours…")
        layout.addWidget(self._lbl)

        self._btn = QPushButton("Fermer")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self.accept)
        layout.addWidget(self._btn)

        self._worker = ConvertWorker(filepath, output_dir)
        self._worker.progress_updated.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, result: Path) -> None:
        self.result_path = result
        size_mb = round(result.stat().st_size / 1024 / 1024, 2)
        self._lbl.setText(f"✓ Converti → {result.name}  ({size_mb} Mo)")
        self._btn.setEnabled(True)

    def _on_failed(self, msg: str) -> None:
        self._lbl.setText(f"✗ Erreur : {msg}")
        self._btn.setEnabled(True)


class DeleteConfirmDialog:
    """Boîte de confirmation suppression (wrapper QMessageBox)."""

    @staticmethod
    def confirm(filepath: Path, parent=None) -> bool:
        msg = QMessageBox(parent)
        msg.setWindowTitle("Confirmer la suppression")
        msg.setText(f"Supprimer définitivement :\n\n<b>{filepath.name}</b>")
        msg.setInformativeText("Cette opération est irréversible.")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Supprimer")
        msg.button(QMessageBox.StandardButton.No).setText("Annuler")
        return msg.exec() == QMessageBox.StandardButton.Yes
