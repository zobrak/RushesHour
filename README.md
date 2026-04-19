# RushesHour

Outil de tri interactif de rush vidéo — CLI et GUI PyQt6.

Parcourt récursivement un dossier, lit chaque fichier dans mpv, détecte et
propose de réparer les fichiers corrompus via ffmpeg, puis offre un menu
d'actions : passer au suivant, laisser sur place, renommer, déplacer,
supprimer, convertir en MP4, ou exporter un segment IN/OUT par stream copy.

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

### Option 1 — Scripts de lancement (recommandé)

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour
bash run_gui.sh [dossier]   # GUI — vérifie libmpv2, ffmpeg, ffprobe
bash run.sh [dossier]       # CLI
bash run.sh --gui [dossier] # GUI via run.sh (alias de run_gui.sh)
```

Les deux scripts créent automatiquement un venv isolé dans `.venv/` et
installent les dépendances Python au premier lancement. `run_gui.sh` vérifie
en outre la présence de `libmpv2` et affiche les commandes d'installation
manquantes si nécessaire.

### Option 2 — Mode développement

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour
pip install -e ".[gui]"
```

---

## GUI (recommandée)

```bash
bash run_gui.sh [dossier]           # recommandé (vérifie les dépendances)
python rusheshour_gui.py [dossier]  # lancement direct
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
| `E` | Exporter le segment IN/OUT (actif dès que IN < OUT sont posés) |
| `Espace` | Pause / lecture |
| `F` | Plein écran / fenêtré |
| `Escape` | Quitter le plein écran |
| `I` | Marquer le point d'entrée IN (focus timeline requis) |
| `O` | Marquer le point de sortie OUT (focus timeline requis) |
| `Ctrl+O` | Ouvrir un dossier |
| `Ctrl+Q` | Quitter |

### Export de segment IN/OUT

Posez un point d'entrée (`I`) et un point de sortie (`O` ou clic droit sur la
timeline), puis appuyez sur `E` ou cliquez **Exporter clip**. L'export utilise
ffmpeg en stream copy (pas de réencodage) : extraction quasi-instantanée, même
qualité que l'original. Le clip produit est placé dans le dossier de destination
si celui-ci est défini, sinon à côté du fichier source. Son nom reprend le stem
de l'original avec le suffixe `_clip_MMmSSs-MMmSSs` (ex.
`interview_clip_01m30s-02m45s.mkv`).

> **Note** : le stream copy est arrondi au keyframe précédant le point IN — un
> écart de quelques frames est possible selon le GOP source. Pour une coupe
> exacte au frame près, une conversion complète serait nécessaire.

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
│   │   ├── scanner.py           # collect_videos, VIDEO_EXTENSIONS, find_orphan_temps
│   │   ├── probe.py             # get_video_info, check_errors, format_duration
│   │   ├── repair.py            # action_repair, REPAIR_STRATEGIES (4 stratégies)
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
│       ├── file_panel.py        # FilePanel (QListWidget, codes couleur O(1))
│       └── dialogs.py           # RepairDialog, ConvertDialog, ExportDialog, DeleteConfirmDialog, OrphanCleanupDialog
├── tests/
│   ├── test_probe.py            # format_duration, is_already_mp4 (unitaire + intégration)
│   ├── test_scanner.py          # collect_videos, find_orphan_temps
│   ├── test_convert.py          # action_convert_mp4 (intégration)
│   ├── test_repair.py           # action_repair (intégration)
│   └── test_export.py           # clip_output_path (unitaire) + action_export_clip (intégration)
├── sort_rush.py                 # Shim CLI
├── rusheshour_gui.py            # Point d'entrée GUI
├── packaging/
│   └── build_deb.sh             # Construit dist/rusheshour_<ver>_amd64.deb
├── run.sh                       # Bootstrap venv portable (CLI, --gui délègue à run_gui.sh)
├── run_gui.sh                   # Bootstrap venv portable (GUI) + vérif. dépendances
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── CHANGELOG.md
```

---

## Lancer les tests

```bash
pip install pytest
pytest tests/ -v                    # tous les tests (unitaires + intégration)
pytest tests/ -v -m "not integration"  # unitaires seulement (sans ffmpeg)
pytest tests/ -v -m integration    # intégration seulement
```

---

## Licence

GPLv3 — voir [LICENSE](LICENSE).

---

## Paquet .deb (Debian 13+)

```bash
# Construire le .deb depuis les sources
bash packaging/build_deb.sh

# Installer (résout les dépendances apt automatiquement)
sudo apt install ./dist/rusheshour_1.0.0_amd64.deb
```

Le paquet déclare `python3-pyqt6`, `python3-mpv`, `libmpv2` et `ffmpeg` comme
dépendances apt. `python3-mpv` est disponible dans Trixie/main ; `libmpv2` et
`ffmpeg` sont déjà présents sur une installation standard Debian 13.

Après installation :

```bash
rusheshour-gui [dossier]   # GUI
sort-rush [options] dossier # CLI
```
