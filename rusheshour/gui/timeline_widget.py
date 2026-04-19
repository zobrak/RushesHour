from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QFont


def _fmt_hms(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class TimelineWidget(QWidget):
    """
    Barre de progression cliquable dessinée via QPainter.

    Clic gauche  → seek à la position cliquée.
    Clic droit   → mark_out.
    Touches I/O  → mark_in / mark_out (focus requis).

    Placeholder visuel IN/OUT prévu pour P3.
    """

    seek_requested    = pyqtSignal(float)
    selection_changed = pyqtSignal(object, object)   # mark_in | None, mark_out | None

    _BAR_H   = 8
    _MARGIN  = 10
    _CURSOR_R = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(52)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)

        self._duration: float = 0.0
        self._position: float = 0.0
        self.mark_in:  float | None = None
        self.mark_out: float | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.update)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def set_duration(self, duration: float) -> None:
        self._duration = max(0.0, duration)
        if self._duration > 0:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def set_position(self, pos: float) -> None:
        self._position = max(0.0, pos)
        self.update()

    def reset(self) -> None:
        self._duration = 0.0
        self._position = 0.0
        self.mark_in  = None
        self.mark_out = None
        self._timer.stop()
        self.update()

    # ------------------------------------------------------------------
    # Peinture
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w      = self.width()
        h      = self.height()
        m      = self._MARGIN
        bar_w  = w - 2 * m
        bar_y  = h // 2 - self._BAR_H // 2
        center = h // 2

        # Fond piste
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3a3a3a"))
        painter.drawRoundedRect(m, bar_y, bar_w, self._BAR_H, 4, 4)

        if self._duration > 0:
            ratio = min(self._position / self._duration, 1.0)

            # Zone IN/OUT (placeholder P3)
            if self.mark_in is not None and self.mark_out is not None:
                in_x  = m + int((self.mark_in  / self._duration) * bar_w)
                out_x = m + int((self.mark_out / self._duration) * bar_w)
                painter.setBrush(QColor(100, 180, 255, 70))
                painter.drawRect(in_x, bar_y, max(0, out_x - in_x), self._BAR_H)

            # Remplissage progressif
            fill_w = int(ratio * bar_w)
            painter.setBrush(QColor("#1e88e5"))
            painter.drawRoundedRect(m, bar_y, max(0, fill_w), self._BAR_H, 4, 4)

            # Curseur
            cx = m + int(ratio * bar_w)
            painter.setBrush(QColor("white"))
            r = self._CURSOR_R
            painter.drawEllipse(cx - r, center - r, 2 * r, 2 * r)

        # Timecodes
        font = QFont("monospace", 9)
        painter.setFont(font)
        painter.setPen(QColor("#ccc"))
        painter.drawText(m, bar_y - 3, _fmt_hms(self._position))
        dur_txt = _fmt_hms(self._duration)
        painter.drawText(w - m - len(dur_txt) * 7, bar_y - 3, dur_txt)

        # Labels IN/OUT
        if self._duration > 0:
            if self.mark_in is not None:
                painter.setPen(QColor("#64b5f6"))
                ix = m + int((self.mark_in / self._duration) * bar_w)
                painter.drawText(ix, h - 3, f"IN {_fmt_hms(self.mark_in)}")
            if self.mark_out is not None:
                painter.setPen(QColor("#ef9a9a"))
                ox = m + int((self.mark_out / self._duration) * bar_w)
                painter.drawText(max(m, ox - 60), h - 3, f"OUT {_fmt_hms(self.mark_out)}")

    # ------------------------------------------------------------------
    # Interactions souris / clavier
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if self._duration <= 0:
            return
        pos = self._x_to_pos(event.position().x())
        if event.button() == Qt.MouseButton.LeftButton:
            self.seek_requested.emit(pos)
        elif event.button() == Qt.MouseButton.RightButton:
            self.mark_out = pos
            self.selection_changed.emit(self.mark_in, self.mark_out)
            self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_I:
            self.mark_in = self._position
            self.selection_changed.emit(self.mark_in, self.mark_out)
            self.update()
        elif event.key() == Qt.Key.Key_O:
            self.mark_out = self._position
            self.selection_changed.emit(self.mark_in, self.mark_out)
            self.update()
        else:
            super().keyPressEvent(event)

    def _x_to_pos(self, x: float) -> float:
        bar_w = self.width() - 2 * self._MARGIN
        ratio = max(0.0, min(1.0, (x - self._MARGIN) / bar_w))
        return ratio * self._duration
