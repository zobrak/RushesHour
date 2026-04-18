#!/usr/bin/env python3
"""
Point d'entrée GUI — RushesHour v0.8.0.

Usage :
  python rusheshour_gui.py [dossier]

Note Wayland : force XWayland (QT_QPA_PLATFORM=xcb) avant tout import Qt,
car libmpv via wid= ne fonctionne pas nativement sous Wayland pur.
Environnement cible : Debian 13 + KDE Plasma.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from rusheshour.gui import launch_gui

if __name__ == "__main__":
    launch_gui()
