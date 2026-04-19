"""
Dialogues GUI : réparation, conversion, confirmation suppression, aide, à propos.

RepairWorker / ConvertWorker héritent de QThread et émettent des signaux
Qt — jamais de mise à jour de widget directe depuis le thread de travail.
"""

import re
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QTextBrowser, QMessageBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt


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
        import io
        import contextlib
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
        self._abort      = False
        self._proc: subprocess.Popen | None = None

    def abort(self) -> None:
        """Demande l'arrêt de la conversion en terminant le sous-processus ffmpeg."""
        self._abort = True
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass

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

        proc = None
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, errors="replace")
            self._proc = proc

            if proc.stderr is None:
                raise RuntimeError("Impossible d'ouvrir le flux stderr ffmpeg")
            for line in proc.stderr:
                if self._abort:
                    break
                m = self._TIME_RE.search(line.rstrip())
                if m and duration > 0:
                    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    elapsed = h * 3600 + mn * 60 + s
                    pct = min(99, int(elapsed / duration * 100))
                    self.progress_updated.emit(pct)

            proc.wait()
            self._proc = None

            if self._abort or proc.returncode != 0:
                work_path.unlink(missing_ok=True)
                if not self._abort:
                    self.failed.emit("Conversion échouée (code ffmpeg ≠ 0)")
                return

            if filepath.exists():
                filepath.unlink()

            if use_temp:
                work_path.rename(output_path)

            self.progress_updated.emit(100)
            self.finished.emit(output_path)

        except Exception as exc:
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait()
                except OSError:
                    pass
            work_path.unlink(missing_ok=True)
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    """
    Lance ffmpeg en sous-processus pour exporter un segment IN/OUT.

    Utilise stream copy (-c copy) : pas de réencodage, progression lue
    sur stderr via les lignes time=HH:MM:SS.
    """

    progress_updated = pyqtSignal(int)   # 0-100
    finished         = pyqtSignal(Path)
    failed           = pyqtSignal(str)

    _TIME_RE = re.compile(r"time=(\d+):(\d+):([\d.]+)")

    def __init__(
        self,
        filepath: Path,
        start: float,
        end: float,
        output_dir: Path | None,
    ) -> None:
        super().__init__()
        self._filepath   = filepath
        self._start      = start
        self._end        = end
        self._output_dir = output_dir
        self._abort      = False
        self._proc: subprocess.Popen | None = None

    def abort(self) -> None:
        """Demande l'arrêt de l'export en terminant le sous-processus ffmpeg."""
        self._abort = True
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def run(self) -> None:
        from rusheshour.core.export import clip_output_path

        filepath = self._filepath
        start    = self._start
        end      = self._end
        duration = end - start
        out_path = clip_output_path(filepath, start, end, self._output_dir)

        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-i",  str(filepath),
            "-t",  str(duration),
            "-c",  "copy",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(out_path),
        ]

        proc = None
        try:
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, errors="replace")
            self._proc = proc

            if proc.stderr is None:
                raise RuntimeError("Impossible d'ouvrir le flux stderr ffmpeg")

            for line in proc.stderr:
                if self._abort:
                    break
                m = self._TIME_RE.search(line.rstrip())
                if m and duration > 0:
                    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    elapsed = h * 3600 + mn * 60 + s
                    pct = min(99, int(elapsed / duration * 100))
                    self.progress_updated.emit(pct)

            proc.wait()
            self._proc = None

            if self._abort or proc.returncode != 0:
                out_path.unlink(missing_ok=True)
                if not self._abort:
                    self.failed.emit("Export échoué (code ffmpeg ≠ 0)")
                return

            self.progress_updated.emit(100)
            self.finished.emit(out_path)

        except Exception as exc:
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait()
                except OSError:
                    pass
            out_path.unlink(missing_ok=True)
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
        self._log.setStyleSheet(
            "background:#111; color:#ccc; font-family:monospace; font-size:11px;"
        )
        layout.addWidget(self._log)

        self._btn = QPushButton("Fermer")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self.accept)
        layout.addWidget(self._btn)

        self._worker = RepairWorker(filepath, errors)
        self._worker.log_line.connect(self._log.append)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._worker.start()

    def closeEvent(self, event) -> None:
        if self._worker.isRunning():
            # action_repair() ne peut pas être interrompue ; on déconnecte
            # les signaux pour éviter tout accès au widget après destruction.
            try:
                self._worker.log_line.disconnect(self._log.append)
                self._worker.finished.disconnect(self._on_finished)
                self._worker.failed.disconnect(self._on_failed)
            except RuntimeError:
                pass
        super().closeEvent(event)

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

    def closeEvent(self, event) -> None:
        if self._worker.isRunning():
            try:
                self._worker.progress_updated.disconnect(self._progress.setValue)
                self._worker.finished.disconnect(self._on_finished)
                self._worker.failed.disconnect(self._on_failed)
            except RuntimeError:
                pass
            self._worker.abort()
            self._worker.wait(5000)
            self._worker.deleteLater()
        super().closeEvent(event)

    def _on_finished(self, result: Path) -> None:
        self.result_path = result
        try:
            size_mb = round(result.stat().st_size / 1024 / 1024, 2)
            self._lbl.setText(f"✓ Converti → {result.name}  ({size_mb} Mo)")
        except FileNotFoundError:
            self._lbl.setText(f"✓ Converti → {result.name}")
        self._btn.setEnabled(True)
        self._worker.deleteLater()

    def _on_failed(self, msg: str) -> None:
        self._lbl.setText(f"✗ Erreur : {msg}")
        self._btn.setEnabled(True)
        self._worker.deleteLater()


class ExportDialog(QDialog):
    """Dialogue d'export de clip IN/OUT avec barre de progression réelle."""

    def __init__(
        self,
        filepath: Path,
        start: float,
        end: float,
        output_dir: Path | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export clip")
        self.setMinimumWidth(440)
        self.result_path: Path | None = None

        from rusheshour.core.export import clip_output_path
        from rusheshour.core.probe  import format_duration

        out_name = clip_output_path(filepath, start, end, output_dir).name
        seg_lbl  = (
            f"{format_duration(start)} → {format_duration(end)}"
            f"  ({format_duration(end - start)})"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Export :</b> {filepath.name}"))
        layout.addWidget(QLabel(f"Segment : {seg_lbl}"))
        layout.addWidget(QLabel(f"Fichier cible : <i>{out_name}</i>"))

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._lbl = QLabel("En cours…")
        layout.addWidget(self._lbl)

        self._btn = QPushButton("Fermer")
        self._btn.setEnabled(False)
        self._btn.clicked.connect(self.accept)
        layout.addWidget(self._btn)

        self._worker = ExportWorker(filepath, start, end, output_dir)
        self._worker.progress_updated.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def closeEvent(self, event) -> None:
        if self._worker.isRunning():
            try:
                self._worker.progress_updated.disconnect(self._progress.setValue)
                self._worker.finished.disconnect(self._on_finished)
                self._worker.failed.disconnect(self._on_failed)
            except RuntimeError:
                pass
            self._worker.abort()
            self._worker.wait(5000)
            self._worker.deleteLater()
        super().closeEvent(event)

    def _on_finished(self, result: Path) -> None:
        self.result_path = result
        try:
            size_mb = round(result.stat().st_size / 1024 / 1024, 2)
            self._lbl.setText(f"✓ Clip exporté → {result.name}  ({size_mb} Mo)")
        except FileNotFoundError:
            self._lbl.setText(f"✓ Clip exporté → {result.name}")
        self._btn.setEnabled(True)
        self._worker.deleteLater()

    def _on_failed(self, msg: str) -> None:
        self._lbl.setText(f"✗ Erreur : {msg}")
        self._btn.setEnabled(True)
        self._worker.deleteLater()


class OrphanCleanupDialog(QDialog):
    """Signale les fichiers temporaires orphelins et propose leur suppression."""

    def __init__(self, orphans: list[Path], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fichiers temporaires orphelins")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        n = len(orphans)
        layout.addWidget(QLabel(
            f"<b>{n} fichier(s) temporaire(s) orphelin(s)</b> détecté(s) "
            "(laissés par une opération interrompue) :"
        ))

        log = QTextEdit()
        log.setReadOnly(True)
        log.setMaximumHeight(180)
        log.setStyleSheet(
            "background:#111; color:#ccc; font-family:monospace; font-size:11px;"
        )
        lines = []
        for p in orphans:
            try:
                size_kb = round(p.stat().st_size / 1024, 1)
                lines.append(f"{p.name}  ({size_kb} Ko)")
            except OSError:
                lines.append(p.name)
        log.setPlainText("\n".join(lines))
        layout.addWidget(log)

        self._orphans = list(orphans)

        btn_row = QHBoxLayout()
        btn_delete = QPushButton("Supprimer tout")
        btn_ignore = QPushButton("Ignorer")
        btn_row.addWidget(btn_delete)
        btn_row.addWidget(btn_ignore)
        layout.addLayout(btn_row)

        btn_delete.clicked.connect(self._delete_all)
        btn_ignore.clicked.connect(self.reject)

    def _delete_all(self) -> None:
        for p in self._orphans:
            try:
                p.unlink()
            except OSError:
                pass
        self.accept()


_HELP_HTML = """
<style>
body  { color:#ddd; background:#1a1a1a; font-family:sans-serif; font-size:12px;
        margin:6px 10px; }
h2    { color:#64b5f6; border-bottom:1px solid #333; padding-bottom:3px;
        margin-top:14px; }
table { border-collapse:collapse; width:100%; margin-bottom:6px; }
td,th { padding:4px 10px; border:1px solid #2a2a2a; }
th    { background:#252525; color:#aaa; font-weight:normal; }
tr:hover td { background:#232323; }
kbd   { background:#2d2d2d; color:#ddd; padding:1px 6px; border-radius:3px;
        font-family:monospace; border:1px solid #444; }
p     { margin:4px 0 8px 0; }
.note { color:#888; font-style:italic; font-size:11px; }
ul    { margin:4px 0 8px 16px; padding:0; }
li    { margin-bottom:3px; }
</style>

<h2>Raccourcis clavier</h2>
<table>
<tr><th>Touche</th><th>Action</th></tr>
<tr><td><kbd>0</kbd></td><td>Suivant — déplace le fichier vers la destination si définie</td></tr>
<tr><td><kbd>1</kbd></td><td>Ne rien faire — laisser le fichier en place</td></tr>
<tr><td><kbd>2</kbd></td><td>Renommer le fichier</td></tr>
<tr><td><kbd>3</kbd></td><td>Déplacer manuellement vers un dossier au choix</td></tr>
<tr><td><kbd>5</kbd></td><td>Supprimer (confirmation requise)</td></tr>
<tr><td><kbd>6</kbd></td><td>Convertir en MP4 / H.264</td></tr>
<tr><td><kbd>7</kbd></td><td>Rejouer depuis le début</td></tr>
<tr><td><kbd>E</kbd></td><td>Exporter le segment IN/OUT (actif dès que IN &lt; OUT)</td></tr>
<tr><td><kbd>I</kbd></td><td>Poser le point d'entrée IN <span class="note">(focus timeline requis)</span></td></tr>
<tr><td><kbd>O</kbd></td><td>Poser le point de sortie OUT <span class="note">(ou clic droit sur la timeline)</span></td></tr>
<tr><td><kbd>Espace</kbd></td><td>Pause / lecture</td></tr>
<tr><td><kbd>F</kbd></td><td>Plein écran / fenêtré</td></tr>
<tr><td><kbd>Échap</kbd></td><td>Quitter le plein écran</td></tr>
<tr><td><kbd>Ctrl+O</kbd></td><td>Ouvrir un dossier</td></tr>
<tr><td><kbd>Ctrl+Q</kbd></td><td>Quitter</td></tr>
<tr><td><kbd>F1</kbd></td><td>Afficher cette aide</td></tr>
</table>

<h2>Flux de travail recommandé</h2>
<ul>
  <li>Ouvrir un dossier de rushes (<kbd>Ctrl+O</kbd> ou <b>Fichier → Ouvrir</b>).</li>
  <li>Optionnel : définir un dossier de destination (<b>Options → Définir la destination</b>).
      Les fichiers validés avec <kbd>0</kbd> y seront déplacés automatiquement.</li>
  <li>Pour chaque fichier : regarder, décider, appuyer sur un raccourci.</li>
  <li>La liste à gauche suit la progression ; les fichiers traités sont grisés.</li>
</ul>

<h2>Export de segment IN/OUT</h2>
<ul>
  <li>Cliquer sur la timeline pour lui donner le focus.</li>
  <li>Appuyer sur <kbd>I</kbd> au moment voulu pour poser le point d'entrée.</li>
  <li>Appuyer sur <kbd>O</kbd> (ou clic droit) pour poser le point de sortie.</li>
  <li>La barre d'infos affiche en bleu la durée et le poids estimé du segment.</li>
  <li>Appuyer sur <kbd>E</kbd> ou cliquer <b>Exporter clip</b> pour lancer l'export.</li>
</ul>
<p class="note">L'export utilise ffmpeg en stream copy (pas de réencodage) : qualité identique à
l'original, durée quasi-instantanée. Le point IN est arrondi au keyframe précédent ;
un écart de quelques frames est possible selon le GOP source.</p>

<h2>Réparation automatique</h2>
<p>Activée par défaut (<b>Options → Réparation automatique</b>). Quand des erreurs sont
détectées, le bouton <b>Réparer</b> s'affiche en rouge. Quatre stratégies ffmpeg sont
essayées successivement ; la première qui réussit est conservée.</p>

<h2>Conversion MP4</h2>
<p>Activée par défaut (<b>Options → Proposition de conversion MP4</b>). Proposée
automatiquement via <kbd>0</kbd> si le fichier n'est pas déjà en MP4/H.264 (détecté
par l'atome <code>ftyp</code> du header, pas par l'extension). Encodage H.264 / AAC,
CRF 23, preset medium.</p>

<h2>Fichiers temporaires</h2>
<p>Au chargement d'un dossier, RushesHour détecte les fichiers temporaires laissés par
une opération ffmpeg interrompue (<code>*.repair_tmp.*</code>,
<code>*.tmp_converting.mp4</code>) et propose de les supprimer.</p>
"""


class HelpDialog(QDialog):
    """Fenêtre d'aide contextuelle — raccourcis, workflow, export IN/OUT."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aide — RushesHour")
        self.setMinimumSize(640, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("background:#1a1a1a; color:#ddd; border:none;")
        browser.setHtml(_HELP_HTML)
        layout.addWidget(browser)

        btn = QPushButton("Fermer")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)


_ABOUT_HTML = """
<style>
body  {{ color:#ddd; background:#1e1e1e; font-family:sans-serif;
         font-size:12px; margin:10px 16px; }}
h1    {{ color:#fff; font-size:18px; margin-bottom:2px; }}
.sub  {{ color:#888; font-size:12px; margin-top:0; }}
.sec  {{ color:#64b5f6; font-weight:bold; margin-top:14px; }}
table {{ border-collapse:collapse; }}
td    {{ padding:2px 10px 2px 0; color:#ccc; }}
td.k  {{ color:#888; white-space:nowrap; }}
a     {{ color:#64b5f6; }}
hr    {{ border:none; border-top:1px solid #333; margin:12px 0; }}
.gpl  {{ color:#888; font-size:11px; line-height:1.5; }}
</style>

<h1>RushesHour <span style="font-size:13px;color:#888;">v{version}</span></h1>
<p class="sub">Outil de tri interactif de rush vidéo</p>

<hr>

<table>
<tr><td class="k">Auteur</td><td>Zobrak &lt;claude@zobrak.net&gt;</td></tr>
<tr><td class="k">Dépôt</td>
    <td><a href="https://github.com/zobrak/RushesHour">github.com/zobrak/RushesHour</a></td></tr>
<tr><td class="k">Licence</td><td>GNU General Public License v3.0 or later</td></tr>
</table>

<hr>

<p class="sec">Dépendances</p>
<table>
<tr><td class="k">mpv / libmpv2</td><td>Lecture vidéo (MpvRenderContext + OpenGL)</td></tr>
<tr><td class="k">python-mpv</td><td>Binding Python pour libmpv</td></tr>
<tr><td class="k">ffmpeg / ffprobe</td><td>Réparation, conversion, export de segments</td></tr>
<tr><td class="k">PyQt6</td><td>Interface graphique (Qt 6)</td></tr>
</table>

<hr>

<p class="gpl">
Ce programme est un logiciel libre&nbsp;: vous pouvez le redistribuer et/ou le modifier
selon les termes de la <b>Licence Publique Générale GNU</b> telle que publiée par la
Free Software Foundation — version&nbsp;3, ou (à votre option) toute version ultérieure.
<br><br>
Ce programme est distribué dans l'espoir qu'il sera utile, mais
<b>SANS AUCUNE GARANTIE</b>&nbsp;; sans même la garantie implicite de
COMMERCIALISABILITÉ ou d'ADÉQUATION À UN USAGE PARTICULIER.
Voir la GNU GPL pour plus de détails&nbsp;:
<a href="https://www.gnu.org/licenses/gpl-3.0.html">gnu.org/licenses/gpl-3.0</a>
</p>
"""


class AboutDialog(QDialog):
    """Dialogue À propos avec notice GPL et liste des dépendances."""

    def __init__(self, parent=None) -> None:
        from rusheshour import __version__
        super().__init__(parent)
        self.setWindowTitle("À propos de RushesHour")
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("background:#1e1e1e; color:#ddd; border:none;")
        browser.setHtml(_ABOUT_HTML.format(version=__version__))
        browser.setFixedHeight(360)
        layout.addWidget(browser)

        btn = QPushButton("Fermer")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)


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
