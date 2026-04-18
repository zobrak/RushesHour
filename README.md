# RushesHour

Outil de tri interactif de rush vidéo — CLI et GUI PyQt6.

Parcourt récursivement un dossier, lit chaque fichier dans mpv, détecte et
propose de réparer les fichiers corrompus via ffmpeg, puis offre un menu
d'actions : passer au suivant, laisser sur place, renommer, déplacer,
supprimer, convertir en MP4.

---

## Prérequis système

| Outil | Rôle | Installation |
|-------|------|--------------|
| `mpv` + `python-mpv` | Lecture vidéo embarquée (GUI) | `sudo apt install mpv` + `pip install python-mpv` |
| `ffmpeg` | Conversion et réparation | `sudo apt install ffmpeg` |
| `ffprobe` | Analyse des fichiers | inclus dans le paquet `ffmpeg` |
| `PyQt6` | Interface graphique | `pip install PyQt6` |
| Python 3.11+ | — | `sudo apt install python3.11` |

> **Note Wayland** : le lecteur utilise l'API render OpenGL de mpv
> (`MpvRenderContext` + `QOpenGLWidget`), indépendant du gestionnaire d'affichage.
> `QT_QPA_PLATFORM=xcb` est forcé dans `rusheshour_gui.py` pour la compatibilité
> KDE Plasma / Debian 13.

---

## Installation

### Option 1 — Script de lancement (recommandé)

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour
bash run.sh /chemin/vers/mes/rushes
```

`run.sh` crée automatiquement un venv isolé dans `.venv/` et installe les
dépendances Python au premier lancement.

### Option 2 — Mode développement

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour
pip install -e ".[gui]"
```

---

## GUI (recommandée)

```bash
python rusheshour_gui.py [dossier]
```

### Raccourcis clavier

| Touche | Action |
|--------|--------|
| `0` | Suivant — déplace vers la destination si définie |
| `1` | Ne rien faire |
| `2` | Renommer |
| `3` | Déplacer manuellement |
| `5` | Supprimer |
| `6` | Convertir en MP4 |
| `7` | Rejouer |
| `Espace` | Pause / lecture |
| `F` | Plein écran / fenêtré |
| `Escape` | Quitter le plein écran |
| `Ctrl+O` | Ouvrir un dossier |
| `Ctrl+Q` | Quitter |

### Menus

- **Fichier** — Ouvrir un dossier
- **Options** — Réparation automatique · Conversion MP4 · Définir la destination
- **Aide** — À propos

---

## CLI

```bash
python sort_rush.py [options] /chemin/vers/dossier
```

### Options

| Option | Description |
|--------|-------------|
| `-d`, `--destination CHEMIN` | Dossier de destination pour les fichiers traités |
| `--no-repair` | Désactive la détection d'erreurs et la réparation automatique |
| `--no-convert` | Désactive la conversion MP4 |
| `--no-menu` | Démarre le traitement directement sans menu principal |
| `--version` | Affiche la version et quitte |

### Aides contextuelles

```bash
python sort_rush.py --help-repair    # Stratégies de réparation ffmpeg
python sort_rush.py --help-convert   # Paramètres d'encodage MP4
python sort_rush.py --help-workflow  # Utilisation incrémentale
```

### Exemples

```bash
# Lancement interactif (menu principal)
python sort_rush.py /media/rushes

# Démarrage direct avec destination prédéfinie
python sort_rush.py /media/rushes --destination /media/trie --no-menu

# Session sans réparation ni conversion
python sort_rush.py /media/rushes --no-repair --no-convert --no-menu
```

---

## Structure du projet

```
RushesHour/
├── rusheshour/                  # Package Python principal
│   ├── __init__.py              # version, metadata
│   ├── core/
│   │   ├── session.py           # dataclass Session
│   │   ├── scanner.py           # collect_videos, VIDEO_EXTENSIONS
│   │   ├── probe.py             # get_video_info, check_errors, format_duration
│   │   ├── repair.py            # action_repair, REPAIR_STRATEGIES (4 stratégies)
│   │   ├── convert.py           # action_convert_mp4, FFMPEG_ENCODE_FLAGS
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
│       ├── file_panel.py        # FilePanel (QListWidget, codes couleur O(1))
│       └── dialogs.py           # RepairDialog, ConvertDialog, DeleteConfirmDialog
├── tests/
│   ├── test_probe.py            # format_duration, is_already_mp4
│   └── test_scanner.py          # collect_videos
├── sort_rush.py                 # Shim CLI
├── rusheshour_gui.py            # Point d'entrée GUI
├── run.sh                       # Bootstrap venv portable
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── CHANGELOG.md
```

---

## Lancer les tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Licence

GPLv3 — voir [LICENSE](LICENSE).

---

## À venir — v0.10.0

- Marqueurs IN/OUT sur la timeline (raccourcis `I` / `O`)
- Export d'extrait en mode copie flux ou réencodage
- Affichage durée et poids estimé de la sélection
