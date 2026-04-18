"""
Interface graphique RushesHour — PyQt6 + python-mpv.

Mode de lancement choisi : Option A
  python rusheshour_gui.py [dossier]

Note Wayland : QT_QPA_PLATFORM=xcb doit être défini avant l'import de Qt
(fait automatiquement dans rusheshour_gui.py).
"""

import os
import sys
from pathlib import Path


def launch_gui(argv: list[str] | None = None) -> None:
    """Point d'entrée GUI. argv = sys.argv si None."""
    from PyQt6.QtWidgets import QApplication
    from rusheshour.gui.main_window import MainWindow
    from rusheshour.core.session    import Session

    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    app.setApplicationName("RushesHour")
    app.setApplicationVersion("0.8.0")

    # Dossier source passé en argument positionnel
    root = Path(".")
    if len(argv) > 1:
        candidate = Path(argv[1])
        if candidate.is_dir():
            root = candidate.resolve()

    session = Session(root=root)
    window  = MainWindow(session)
    window.show()

    # os._exit() au lieu de sys.exit() : python-mpv crée un thread d'événements
    # non-daemon ; sys.exit() attendrait indéfiniment sa fin après terminate().
    os._exit(app.exec())
