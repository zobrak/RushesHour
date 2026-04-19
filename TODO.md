# RushesHour — TODO

Version courante : **0.9.12**

---

## État des priorités

| Priorité | Titre | État |
|----------|-------|------|
| P1 | Structure du dépôt et refactoring CLI | ✅ Fait |
| P2 | GUI PyQt6 + lecteur vidéo embarqué | ✅ Fait |
| P3 | Export de segment IN/OUT | ✅ Fait |
| P4 | Qualité et distribution | 🔄 En cours |

---

## P4 — Qualité et distribution (en cours)

- [x] Affichage durée et poids estimé de la sélection IN/OUT dans la GUI
  (bitrate × durée / 8, affiché en temps réel dès que IN < OUT)
- [ ] Nettoyage des fichiers temporaires orphelins au démarrage
  (patterns `*.repair_tmp.*` et `*.tmp_converting.mp4` laissés par SIGKILL)
- [ ] Support `run.sh --gui` pour lancer la GUI depuis le script bootstrap
- [ ] Packaging autonome (PyInstaller / Nuitka) — hors scope immédiat

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
