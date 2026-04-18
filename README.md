# RushesHour

Outil de tri interactif de rush vidéo.

Parcourt récursivement un dossier, lit chaque fichier dans mpv, détecte et
propose de réparer les fichiers corrompus via ffmpeg, puis offre un menu
d'actions : passer au suivant, laisser sur place, renommer, déplacer,
supprimer, convertir en MP4.

---

## Prérequis système

- `mpv` — lecture vidéo : `sudo apt install mpv`
- `ffmpeg` — conversion et réparation : `sudo apt install ffmpeg`
- `ffprobe` — analyse des fichiers (inclus dans le paquet `ffmpeg`)
- Python 3.11+

---

## Installation

### Option 1 — Script de lancement (recommandé, aucune installation globale)

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour
bash run.sh /chemin/vers/mes/rushes
```

`run.sh` crée automatiquement un venv isolé dans `.venv/` et installe les
dépendances Python au premier lancement.

### Option 2 — Installation en mode développement

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour
pip install -e .
sort-rush /chemin/vers/mes/rushes
```

---

## Usage CLI

```
python sort_rush.py [options] /chemin/vers/dossier
```

### Options principales

| Option | Description |
|--------|-------------|
| `-d`, `--destination CHEMIN` | Dossier de destination pour les fichiers traités |
| `--no-repair` | Désactive la détection d'erreurs et la réparation automatique |
| `--no-convert` | Désactive la conversion MP4 |
| `--no-menu` | Démarre le traitement directement sans menu principal |
| `--version` | Affiche la version et quitte |

### Aides contextuelles

```bash
python sort_rush.py --help-repair    # Détail des stratégies de réparation ffmpeg
python sort_rush.py --help-convert   # Paramètres d'encodage de la conversion MP4
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
├── rusheshour/              # Package Python principal
│   ├── __init__.py
│   ├── cli/
│   │   ├── main.py          # check_dependencies, process_video, run_session, main
│   │   ├── menus.py         # ask, confirm, show_menu, main_menu, menu_options
│   │   └── parser.py        # build_parser, constantes d'aide CLI
│   ├── core/
│   │   ├── session.py       # dataclass Session
│   │   ├── scanner.py       # collect_videos, VIDEO_EXTENSIONS
│   │   ├── probe.py         # get_video_info, check_errors, format_duration
│   │   ├── repair.py        # action_repair, REPAIR_STRATEGIES
│   │   ├── convert.py       # action_convert_mp4, FFMPEG_ENCODE_FLAGS
│   │   └── actions.py       # action_rename, action_move_to, action_delete, finalize
│   └── gui/                 # GUI PyQt6 — à venir (v0.8.0)
├── tests/
│   ├── test_probe.py
│   └── test_scanner.py
├── sort_rush.py             # Shim CLI
├── rusheshour_gui.py        # Shim GUI (placeholder)
├── run.sh                   # Bootstrap venv portable
└── pyproject.toml
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

## À venir

### v0.8.0 — GUI PyQt6
- Interface graphique avec lecteur vidéo embarqué (python-mpv)
- Timeline cliquable
- Panneau de fichiers avec statuts visuels
- Toutes les actions CLI portées dans la GUI

### v0.9.0 — Sélection et export d'extrait
- Marqueurs IN/OUT sur la timeline (raccourcis `I` / `O`)
- Export d'extrait en mode copie flux ou réencodage
- Affichage durée et poids estimé de la sélection

> Note Wayland : le lecteur mpv embarqué fonctionne nativement sous X11.
> Sous Wayland pur, XWayland est requis (`QT_QPA_PLATFORM=xcb`).
> Environnement cible : Debian 13 + KDE Plasma.
