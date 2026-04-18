from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QFont


_COLOR_CURRENT = QColor("#1e88e5")
_COLOR_DONE    = QColor("#4caf50")
_COLOR_ERROR   = QColor("#f44336")
_COLOR_PENDING = QColor("#dddddd")


class FilePanel(QWidget):
    """
    Panneau de gauche affichant la liste des fichiers vidéo.

    Codes couleur :
      bleu  (#1e88e5) — fichier courant
      vert  (#4caf50) — traité (done)
      rouge (#f44336) — erreur détectée
      blanc           — en attente
    """

    file_selected = pyqtSignal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._label = QLabel("Aucun dossier ouvert")
        self._label.setStyleSheet("padding: 4px 6px; color: #888; font-size: 11px;")
        layout.addWidget(self._label)

        self._list = QListWidget()
        self._list.setMinimumWidth(220)
        self._list.setStyleSheet("""
            QListWidget { background: #1e1e1e; color: #ddd; border: none; }
            QListWidget::item { padding: 4px 6px; }
            QListWidget::item:selected { background: #2a2a2a; }
        """)
        layout.addWidget(self._list)

        self._files:   list[Path]     = []
        self._status:  dict[int, str] = {}   # index → "pending"|"done"|"error"
        self._current: int = -1

        self._list.currentRowChanged.connect(self._on_row_changed)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_files(self, files: list[Path]) -> None:
        self._files   = list(files)
        self._status  = {}
        self._current = -1
        self._label.setText(f"{len(files)} fichier(s)")
        self._rebuild()

    def set_current(self, index: int) -> None:
        prev = self._current
        self._current = index
        if prev != index:
            item = self._list.item(prev)
            if item is not None:
                self._apply_style(item, prev)
        item = self._list.item(index)
        if item is not None:
            self._apply_style(item, index)
            self._list.blockSignals(True)
            self._list.setCurrentRow(index)
            self._list.scrollToItem(item)
            self._list.blockSignals(False)

    def mark_status(self, index: int, status: str) -> None:
        """status : "pending" | "done" | "error" """
        self._status[index] = status
        item = self._list.item(index)
        if item is not None:
            self._apply_style(item, index)

    def update_path(self, index: int, new_path: Path) -> None:
        if 0 <= index < len(self._files):
            self._files[index] = new_path
            item = self._list.item(index)
            if item is not None:
                item.setText(new_path.name)
                item.setToolTip(str(new_path))

    # ------------------------------------------------------------------
    # Rendu interne
    # ------------------------------------------------------------------

    def _apply_style(self, item: QListWidgetItem, index: int) -> None:
        status = self._status.get(index, "pending")
        font   = item.font()
        if index == self._current:
            item.setForeground(_COLOR_CURRENT)
            font.setBold(True)
        elif status == "done":
            item.setForeground(_COLOR_DONE)
            font.setBold(False)
        elif status == "error":
            item.setForeground(_COLOR_ERROR)
            font.setBold(False)
        else:
            item.setForeground(_COLOR_PENDING)
            font.setBold(False)
        item.setFont(font)

    def _rebuild(self) -> None:
        """Reconstruit entièrement la liste. Appelé uniquement par set_files()."""
        self._list.blockSignals(True)
        self._list.clear()

        for i, f in enumerate(self._files):
            item = QListWidgetItem(f.name)
            item.setToolTip(str(f))
            self._apply_style(item, i)
            self._list.addItem(item)

        if 0 <= self._current < self._list.count():
            self._list.setCurrentRow(self._current)
            self._list.scrollToItem(self._list.currentItem())

        self._list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._files):
            self._current = row
            self.file_selected.emit(self._files[row])
