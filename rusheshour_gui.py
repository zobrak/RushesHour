#!/usr/bin/env python3
"""
Point d'entrée GUI — RushesHour v0.9.0.

Usage :
  python rusheshour_gui.py [dossier]

Note Wayland : force XWayland (QT_QPA_PLATFORM=xcb) avant tout import Qt.
Le rendu vidéo utilise l'API OpenGL de mpv (MpvRenderContext + QOpenGLWidget),
indépendant du gestionnaire d'affichage.
Environnement cible : Debian 13 + KDE Plasma.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from rusheshour.gui import launch_gui

if __name__ == "__main__":
    launch_gui()
