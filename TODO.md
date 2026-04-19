# RushesHour — TODO

Version courante : **1.1.0**

---

## État des priorités

| Priorité | Titre | État |
|----------|-------|------|
| P1 | Structure du dépôt et refactoring CLI | ✅ Fait |
| P2 | GUI PyQt6 + lecteur vidéo embarqué | ✅ Fait |
| P3 | Export de segment IN/OUT | ✅ Fait |
| P4 | Qualité et distribution | ✅ Fait |
| P5 | Portabilité élargie (AppImage · Windows · Flatpak) | 🔲 Planifié |

---

## P4 — Qualité et distribution ✅

- [x] Affichage durée et poids estimé de la sélection IN/OUT dans la GUI
- [x] Nettoyage des fichiers temporaires orphelins au démarrage
- [x] Support `run.sh --gui` pour lancer la GUI depuis le script bootstrap
- [x] Packaging `.deb` Debian 13 (`packaging/build_deb.sh`)

---

## P5 — Portabilité élargie (planifié)

Ordre de priorité recommandé : AppImage → Windows → Flatpak.

### Prérequis communs (code)

- [ ] **Dé-hardcoder `QT_QPA_PLATFORM=xcb`** dans `rusheshour_gui.py`
  Conditionner à `sys.platform != "win32"` ; sur Wayland laisser Qt détecter.
  Bloqueur pour Windows et Flatpak.

### AppImage (Linux cross-distro) — ~5 h

- [ ] Ajouter fallback ctypes dans le point d'entrée AppImage pour résoudre
  `libmpv.so.2` depuis `$APPDIR/lib/` (python-mpv ne trouve pas la lib dans
  le sandbox AppImage par défaut)
- [ ] Écrire `packaging/appimage/AppImageBuilder.yml` (appimage-builder)
  ou recipe `linuxdeploy` + `linuxdeploy-plugin-qt`
- [ ] Bundler `libmpv.so.2` + binaires statiques `ffmpeg`/`ffprobe`
- [ ] Bundler plugins Qt (xcb, wayland) via `linuxdeploy-plugin-qt`
- [ ] **Builder sur Ubuntu 22.04** (GLIBC 2.35) pour garantir la compatibilité
  Debian 10 / Ubuntu 22.04+ / Fedora 38+ — ne pas builder sur Debian 13
  (GLIBC trop récent, l'AppImage ne tourne pas sur Ubuntu 22.04)
- [ ] Publier `dist/RushesHour-1.x.x-x86_64.AppImage` en GitHub Release

### Windows (PyInstaller) — ~7 h

- [ ] Récupérer `libmpv-2.dll` depuis mpv.io (builds Windows officiels)
- [ ] Récupérer binaires statiques `ffmpeg.exe` / `ffprobe.exe` (ffmpeg-static)
- [ ] Écrire `packaging/windows/rusheshour.spec` (PyInstaller)
  — `--add-binary libmpv-2.dll:.`
  — `--add-binary ffmpeg.exe:bin`
  — `--hidden-import=PyQt6.sip`
  — bundler plugin `platforms/qwindows.dll`
- [ ] Vérifier `QOpenGLWidget` + `MpvRenderContext` sur GPU sans ANGLE
  (Qt6 Windows supprime la couche OpenGL→Direct3D)
- [ ] Créer installeur NSIS ou utiliser `winget` pour distribution
- [ ] Tester sur Windows 10 + Windows 11

### Flatpak (Flathub) — ~7 h

- [ ] Écrire `packaging/flatpak/net.zobrak.RushesHour.yml`
  — runtime : `org.kde.Platform` (Qt6 inclus)
  — extension ffmpeg : `org.freedesktop.Platform.ffmpeg-full`
  — module libmpv : builder depuis source (référence : KDE Haruna)
  — dépendances Python (PyQt6, python-mpv) : via pip dans le manifest
- [ ] Supprimer le forçage `QT_QPA_PLATFORM=xcb` (incompatible Wayland Flatpak)
- [ ] Soumettre sur Flathub après validation locale

---

## Arborescence actuelle

```
RushesHour/
├── rusheshour/
│   ├── __init__.py              # __version__ = "0.9.10"
│   ├── core/
│   │   ├── __init__.py          # re-exports publics
│   │   ├── session.py           # dataclass Session
│   │   ├── scanner.py           # collect_videos, VIDEO_EXTENSIONS
│   │   ├── probe.py             # get_video_info, check_errors, is_already_mp4,
│   │   │                        # format_duration, _MP4_MAJOR_BRANDS
│   │   ├── repair.py            # action_repair, REPAIR_STRATEGIES
│   │   ├── convert.py           # action_convert_mp4, FFMPEG_ENCODE_FLAGS
│   │   ├── export.py            # action_export_clip, clip_output_path
│   │   └── actions.py           # action_rename, action_move_to, action_delete, finalize
│   ├── cli/
│   │   ├── main.py              # check_dependencies, process_video, run_session, main
│   │   ├── menus.py             # ask, confirm, show_menu, main_menu, menu_options
│   │   └── parser.py            # build_parser, BANNER, HELP_TEXT, HELP_REPAIR…
│   └── gui/
│       ├── __init__.py          # launch_gui(), QSurfaceFormat OpenGL 3.3
│       ├── main_window.py       # MainWindow, _FileInfoWorker
│       ├── player_widget.py     # PlayerWidget (QOpenGLWidget + MpvRenderContext)
│       ├── timeline_widget.py   # TimelineWidget (QPainter, marqueurs IN/OUT)
│       ├── file_panel.py        # FilePanel (QListWidget, codes couleur)
│       └── dialogs.py           # RepairDialog, ConvertDialog, ExportDialog,
│                                # DeleteConfirmDialog + workers QThread
├── tests/
│   ├── conftest.py              # fixtures valid_mp4, valid_mkv (ffmpeg)
│   ├── test_probe.py            # format_duration, is_already_mp4
│   ├── test_scanner.py          # collect_videos
│   ├── test_convert.py          # action_convert_mp4 (intégration)
│   ├── test_repair.py           # action_repair (intégration)
│   └── test_export.py           # clip_output_path + action_export_clip
├── sort_rush.py                 # shim CLI
├── rusheshour_gui.py            # point d'entrée GUI
├── run.sh                       # bootstrap venv CLI
├── run_gui.sh                   # bootstrap venv GUI + vérif. dépendances
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── CHANGELOG.md
├── README.md
└── TODO.md                      # ce fichier
```
