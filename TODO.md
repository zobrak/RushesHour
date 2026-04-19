# RushesHour — TODO

Instructions pour Claude Code. Lire ce fichier en entier avant de commencer.
Traiter les tâches dans l'ordre des priorités. Cocher chaque tâche à la fin
de son exécution. Ne jamais modifier le comportement fonctionnel existant sans
instruction explicite.

---

## Contexte du projet

**Nom :** RushesHour
**Dépôt :** https://github.com/zobrak/RushesHour
**Licence :** GPLv3
**Langage :** Python 3.11+
**Dépendances système :** `mpv`, `ffmpeg` (inclut `ffprobe`)

RushesHour est un outil de tri interactif de rush vidéo. Il existe
actuellement sous forme d'un script CLI monolithique (`sort_rush.py`,
v0.7.1). L'objectif est de le refactoriser en package Python structuré,
puis d'y ajouter une GUI PyQt6 avec lecteur vidéo embarqué.

Le script `sort_rush.py` est la référence fonctionnelle. Son comportement
ne doit pas être altéré pendant le refactoring — uniquement restructuré.

---

## Arborescence cible validée

```
RushesHour/
│
├── rusheshour/                  # Package Python principal
│   ├── __init__.py              # version, metadata
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py              # point d'entrée CLI (contenu de sort_rush.py)
│   │   ├── menus.py             # main_menu(), show_menu(), menu_options()
│   │   └── parser.py            # build_parser(), constantes d'aide CLI
│   ├── core/
│   │   ├── __init__.py
│   │   ├── session.py           # dataclass Session
│   │   ├── scanner.py           # collect_videos()
│   │   ├── probe.py             # get_video_info(), check_errors(),
│   │   │                        # is_already_mp4(), format_duration(),
│   │   │                        # print_video_info()
│   │   ├── repair.py            # action_repair(), _run_repair_strategy(),
│   │   │                        # _verify_repaired(), REPAIR_STRATEGIES
│   │   ├── convert.py           # action_convert_mp4(), FFMPEG_ENCODE_FLAGS
│   │   └── actions.py           # action_rename(), action_move_to(),
│   │                            # action_move_manual(), action_delete(),
│   │                            # finalize()
│   └── gui/                     # GUI PyQt6 — à construire (Priorité 2)
│       ├── __init__.py
│       ├── main_window.py
│       ├── player_widget.py
│       ├── timeline_widget.py
│       ├── file_panel.py
│       └── dialogs.py
│
├── tests/
│   ├── __init__.py
│   ├── test_probe.py
│   ├── test_repair.py
│   ├── test_convert.py
│   └── test_scanner.py
│
├── assets/
│   └── .gitkeep
│
├── sort_rush.py                 # shim CLI — importe et lance rusheshour.cli.main
├── rusheshour_gui.py            # shim GUI — importe et lance rusheshour.gui (P2)
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── run.sh
│
├── README.md
├── CHANGELOG.md
├── TODO.md                      # ce fichier
├── LICENSE                      # GPLv3 (existant)
├── NOTICES                      # licences dépendances (existant)
└── .gitignore
```

---

## Priorité 1 — Structure du dépôt et refactoring CLI

### 1.1 Fichiers de configuration du projet

- [ ] Créer `pyproject.toml` :
  ```toml
  [build-system]
  requires = ["setuptools>=68", "wheel"]
  build-backend = "setuptools.backends.legacy:build"

  [project]
  name = "rusheshour"
  version = "0.7.1"
  description = "Outil de tri interactif de rush vidéo"
  license = { text = "GPL-3.0-or-later" }
  requires-python = ">=3.11"
  dependencies = []

  [project.optional-dependencies]
  gui = ["PyQt6>=6.4", "python-mpv>=1.0.0"]
  dev = ["pytest>=7.0", "pytest-qt"]

  [project.scripts]
  sort-rush = "rusheshour.cli.main:main"

  [tool.setuptools.packages.find]
  where = ["."]
  include = ["rusheshour*"]
  ```

- [ ] Créer `requirements.txt` :
  ```
  PyQt6>=6.4
  python-mpv>=1.0.0
  ```

- [ ] Créer `requirements-dev.txt` :
  ```
  pytest>=7.0
  pytest-qt
  ```

- [ ] Créer `.gitignore` :
  ```gitignore
  # Python
  __pycache__/
  *.py[cod]
  *.pyo
  *.pyd
  .Python
  *.egg-info/
  dist/
  build/
  .eggs/

  # Virtualenv
  .venv/
  venv/
  env/

  # Tests
  .pytest_cache/
  .coverage
  htmlcov/

  # Fichiers temporaires produits par RushesHour
  *.repair_tmp.*
  *.tmp_converting.mp4

  # IDE
  .idea/
  .vscode/
  *.swp
  *.swo

  # OS
  .DS_Store
  Thumbs.db
  ```

- [ ] Créer `run.sh` (bootstrap venv portable, aucune trace hors du dossier) :
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  VENV="$DIR/.venv"
  if [ ! -d "$VENV" ]; then
      echo "[RushesHour] Création du venv..."
      python3 -m venv "$VENV"
      "$VENV/bin/pip" install -q -r "$DIR/requirements.txt"
  fi
  exec "$VENV/bin/python" "$DIR/sort_rush.py" "$@"
  ```
  ```bash
  chmod +x run.sh
  ```

### 1.2 Refactoring du script CLI en package

Objectif : extraire le contenu de `sort_rush.py` dans le package
`rusheshour/` sans modifier aucun comportement. Toutes les fonctions,
constantes et textes restent identiques — seul l'emplacement change.

Règles impératives :
- Ne pas modifier la logique des fonctions pendant le refactoring
- Conserver tous les imports nécessaires dans chaque module
- Vérifier que `python sort_rush.py --help` fonctionne à l'identique
  après refactoring

**Ordre de création des modules (respecter les dépendances) :**

- [ ] Créer `rusheshour/__init__.py` :
  ```python
  """RushesHour — Outil de tri interactif de rush vidéo."""
  __version__ = "0.7.1"
  __author__  = "Zobrak"
  __license__ = "GPL-3.0-or-later"
  ```

- [ ] Créer `rusheshour/core/__init__.py` (vide)

- [ ] Créer `rusheshour/core/session.py` :
  Extraire depuis `sort_rush.py` :
  - `Session` (dataclass)

- [ ] Créer `rusheshour/core/scanner.py` :
  Extraire depuis `sort_rush.py` :
  - `VIDEO_EXTENSIONS`
  - `collect_videos()`

- [ ] Créer `rusheshour/core/probe.py` :
  Extraire depuis `sort_rush.py` :
  - `get_video_info()`
  - `is_already_mp4()`
  - `check_errors()`
  - `format_duration()`
  - `print_video_info()`

- [ ] Créer `rusheshour/core/convert.py` :
  Extraire depuis `sort_rush.py` :
  - `FFMPEG_ENCODE_FLAGS`
  - `action_convert_mp4()`

- [ ] Créer `rusheshour/core/repair.py` :
  Extraire depuis `sort_rush.py` :
  - `REPAIR_STRATEGIES`
  - `_run_repair_strategy()`
  - `_verify_repaired()`
  - `action_repair()`

- [ ] Créer `rusheshour/core/actions.py` :
  Extraire depuis `sort_rush.py` :
  - `action_rename()`
  - `action_move_to()`
  - `action_move_manual()`
  - `action_delete()`
  - `finalize()`

- [ ] Créer `rusheshour/cli/__init__.py` (vide)

- [ ] Créer `rusheshour/cli/parser.py` :
  Extraire depuis `sort_rush.py` :
  - `VERSION` (importer depuis `rusheshour.__init__`)
  - `BANNER`
  - `HELP_TEXT`
  - `HELP_REPAIR`
  - `HELP_CONVERT`
  - `HELP_WORKFLOW`
  - `build_parser()`
  Mettre à jour `prog="sort_rush.py"` et toutes les références au nom
  du script dans les textes d'aide.

- [ ] Créer `rusheshour/cli/menus.py` :
  Extraire depuis `sort_rush.py` :
  - `ask()`
  - `confirm()`
  - `show_menu()`
  - `main_menu()`
  - `menu_options()`
  - `setup_output_dir()`

- [ ] Créer `rusheshour/cli/main.py` :
  Extraire depuis `sort_rush.py` :
  - `check_dependencies()`
  - `process_video()`
  - `run_session()`
  - `main()`
  Point d'entrée : `if __name__ == "__main__": main()`

- [ ] Créer `rusheshour/gui/__init__.py` (vide, placeholder P2)

- [ ] Mettre à jour `sort_rush.py` comme shim d'une ligne :
  ```python
  #!/usr/bin/env python3
  """Point d'entrée CLI — délègue à rusheshour.cli.main."""
  from rusheshour.cli.main import main
  if __name__ == "__main__":
      main()
  ```

- [ ] Créer `rusheshour_gui.py` comme shim placeholder :
  ```python
  #!/usr/bin/env python3
  """Point d'entrée GUI — non encore implémenté (Priorité 2)."""
  print("GUI non disponible dans cette version. Voir TODO.md Priorité 2.")
  ```

### 1.3 Vérification fonctionnelle post-refactoring

- [ ] Vérifier que les imports se résolvent sans erreur :
  ```bash
  python -c "from rusheshour.cli.main import main; print('OK')"
  ```
- [ ] Vérifier que le shim fonctionne :
  ```bash
  python sort_rush.py --version
  python sort_rush.py --help
  python sort_rush.py --help-repair
  python sort_rush.py --help-convert
  python sort_rush.py --help-workflow
  ```
- [ ] Vérifier qu'un dossier vide ne plante pas :
  ```bash
  mkdir /tmp/test_rushes
  python sort_rush.py /tmp/test_rushes --no-menu
  ```

### 1.4 Documentation

- [ ] Créer `CHANGELOG.md` en extrayant le bloc CHANGELOG du docstring
  de `sort_rush.py`, format Keep a Changelog :
  https://keepachangelog.com/fr/1.1.0/

- [ ] Rédiger `README.md` :
  - Description du projet
  - Prérequis système (`mpv`, `ffmpeg`)
  - Installation (clone + `run.sh` ou `pip install -e .`)
  - Usage CLI (`sort_rush.py --help`)
  - Structure du projet
  - Licence
  - Section "À venir" : GUI PyQt6, export d'extrait

- [ ] Compléter `NOTICES` avec les licences des dépendances :
  ```
  mpv       — LGPLv2.1+     https://github.com/mpv-player/mpv
  libmpv    — LGPLv2.1+     https://github.com/mpv-player/mpv
  python-mpv — MIT          https://github.com/jaseg/python-mpv
  PyQt6     — GPLv3         https://riverbankcomputing.com/software/pyqt/
  FFmpeg    — LGPLv2.1+/GPLv2+  https://ffmpeg.org/legal.html
  ```

### 1.5 Tests unitaires initiaux

- [ ] Créer `tests/__init__.py` (vide)

- [ ] Créer `tests/test_probe.py` :
  Tests sur `format_duration()` et `is_already_mp4()` (fonctions pures,
  pas de dépendance système) :
  ```python
  def test_format_duration_seconds(): ...
  def test_format_duration_minutes(): ...
  def test_format_duration_hours(): ...
  def test_is_already_mp4_true(): ...
  def test_is_already_mp4_false_wrong_codec(): ...
  def test_is_already_mp4_false_wrong_container(): ...
  ```

- [ ] Créer `tests/test_scanner.py` :
  Tests sur `collect_videos()` avec un dossier temporaire (`tmp_path`
  fixture pytest) :
  ```python
  def test_collect_videos_empty_dir(): ...
  def test_collect_videos_finds_mp4(): ...
  def test_collect_videos_excludes_dir(): ...
  def test_collect_videos_recursive(): ...
  ```

- [ ] Vérifier que les tests passent :
  ```bash
  pip install pytest
  pytest tests/ -v
  ```

### 1.6 Commit et tag

- [ ] Commit de l'ensemble :
  ```bash
  git add .
  git commit -m "refactor: extract CLI into rusheshour package (v0.7.1)"
  ```
- [ ] Créer le tag Git :
  ```bash
  git tag -a v0.7.1 -m "Release v0.7.1 — CLI fonctionnel, structure package"
  git push origin main --tags
  ```

---

## Priorité 2 — GUI PyQt6 + python-mpv

**Prérequis :** Priorité 1 entièrement complétée et commitée.
**Stack :** PyQt6 + python-mpv (libmpv). Compatible GPLv3.

### 2.1 Vérification de l'environnement

- [ ] Vérifier la présence de `libmpv.so` :
  ```bash
  find /usr -name 'libmpv*' 2>/dev/null
  # Si absent : sudo apt install libmpv-dev
  ```
- [ ] Installer les dépendances dans le venv :
  ```bash
  source .venv/bin/activate
  pip install PyQt6 python-mpv
  ```
- [ ] Vérifier l'import :
  ```python
  python -c "import mpv; import PyQt6; print('OK')"
  ```

### 2.2 Infrastructure GUI

- [ ] Décider et documenter le mode de lancement GUI :
  Option A : `python rusheshour_gui.py`
  Option B : `python sort_rush.py --gui`
  Implémenter l'option choisie.

- [ ] Créer `rusheshour/gui/main_window.py` :
  `MainWindow(QMainWindow)` avec layout en trois panneaux :
  - Gauche : `FilePanel` (liste des fichiers)
  - Centre : `PlayerWidget` (lecteur vidéo)
  - Bas : barre d'infos + boutons d'action
  Barre de menu : Fichier / Options / Aide
  Barre de statut : nom fichier courant, index/total, destination

- [ ] Intégrer `Session` comme modèle central partagé entre tous les widgets

### 2.3 Lecteur vidéo embarqué

- [ ] Créer `rusheshour/gui/player_widget.py` :
  `PlayerWidget(QWidget)` :
  - Créer l'instance mpv : `player = mpv.MPV(wid=int(self.winId()), ...)`
  - Forcer X11 si Wayland détecté : `QT_QPA_PLATFORM=xcb`
    (documenter la limitation Wayland dans le README)
  - Observer `time-pos` → signal Qt `position_changed(float)`
  - Observer `duration` → signal Qt `duration_changed(float)`
  - Observer `pause` → signal Qt `pause_changed(bool)`
  - Méthodes publiques : `load(path)`, `play()`, `pause()`, `seek(pos)`,
    `stop()`
  - Thread safety : tous les observers émettent via `pyqtSignal`,
    jamais de mise à jour widget directe depuis le thread mpv

- [ ] Contrôles de lecture sous le lecteur :
  Boutons lecture/pause, stop, slider volume, label timecode

### 2.4 Timeline

- [ ] Créer `rusheshour/gui/timeline_widget.py` :
  `TimelineWidget(QWidget)` dessiné via `QPainter` :
  - Barre de progression cliquable (seek sur clic)
  - Curseur de position mis à jour toutes les 100ms via `QTimer`
  - Affichage du timecode courant (HH:MM:SS)
  - (P3) Zone de sélection IN/OUT (placeholder visuel à prévoir dès maintenant)

### 2.5 Panneau fichiers

- [ ] Créer `rusheshour/gui/file_panel.py` :
  `FilePanel(QWidget)` :
  - `QListWidget` affichant les fichiers du dossier source
  - Mise en évidence du fichier courant
  - Icône ou couleur différente selon statut (traité / en attente / erreur)

### 2.6 Dialogues

- [ ] Créer `rusheshour/gui/dialogs.py` :
  - `RepairDialog` : progression de la réparation ffmpeg (QProgressDialog
    + QThread), affichage des stratégies tentées
  - `ConvertDialog` : progression de la conversion (QThread + parsing
    de la progression ffmpeg via stderr)
  - `DeleteConfirmDialog` : QMessageBox de confirmation suppression

### 2.7 Actions fichier dans la GUI

Porter toutes les actions de `rusheshour/core/actions.py` dans la GUI :
- [ ] Suivant → `finalize()` + passage au fichier suivant dans `FilePanel`
- [ ] Ne rien faire → passage au suivant sans déplacement
- [ ] Renommer → `QInputDialog.getText()`
- [ ] Déplacer → `QFileDialog.getExistingDirectory()`
- [ ] Supprimer → `DeleteConfirmDialog` + `action_delete()`
- [ ] Convertir → `ConvertDialog` + `action_convert_mp4()` dans QThread
- [ ] Réparation → `RepairDialog` + `action_repair()` dans QThread

### 2.8 Vérification et commit

- [ ] Tester le lancement GUI sans vidéo (fenêtre vide, pas de crash)
- [ ] Tester le chargement d'une vidéo dans le lecteur
- [ ] Tester chaque bouton d'action
- [ ] Commit :
  ```bash
  git add .
  git commit -m "feat: add PyQt6 GUI with embedded mpv player (v0.8.0)"
  git tag -a v0.8.0 -m "Release v0.8.0 — GUI avec lecteur vidéo embarqué"
  git push origin main --tags
  ```

---

## Priorité 3 — Sélection et export d'extrait

**Prérequis :** Priorité 2 entièrement complétée et commitée.

### 3.1 Marqueurs IN / OUT sur la timeline

- [ ] Ajouter dans `TimelineWidget` :
  - Attributs `mark_in: float | None` et `mark_out: float | None`
  - Clic gauche sur la timeline → `mark_in = position_cliquée`
  - Clic droit sur la timeline → `mark_out = position_cliquée`
  - Raccourcis clavier : `I` → mark_in, `O` → mark_out
  - Rendu visuel : rectangle semi-transparent entre IN et OUT
  - Labels timecode IN et OUT affichés aux extrémités de la sélection
  - Signal `selection_changed(mark_in, mark_out)` émis à chaque modification

- [ ] Affichage temps réel des infos de l'extrait dans un widget dédié :
  - Durée : `mark_out - mark_in` formatée en `HH:MM:SS.mmm`
  - Poids estimé : `bitrate_total (bits/s) × durée (s) / 8` en Mo
    (bitrate extrait depuis `get_video_info()`)

### 3.2 Export de l'extrait

- [ ] Créer `rusheshour/core/export.py` :
  ```python
  def export_clip(
      filepath: Path,
      mark_in: float,
      mark_out: float,
      output_path: Path,
      mode: str = "copy",          # "copy" | "reencode"
  ) -> Path: ...
  ```
  Commande ffmpeg générée :
  - Mode `copy` :
    `ffmpeg -ss <in> -to <out> -i input -c copy output`
    (coupe rapide sur keyframe)
  - Mode `reencode` :
    `ffmpeg -ss <in> -to <out> -i input -c:v libx264 -crf 23 ... output`
    (coupe frame-précise, plus lent)

- [ ] Créer `rusheshour/gui/dialogs.py::ExportDialog` :
  - Champ nom du fichier de sortie
  - `QFileDialog` pour le dossier de sortie
  - Radio buttons : copie flux / réencodage
  - Affichage durée et poids estimé de l'extrait
  - Bouton Exporter actif uniquement si `mark_in < mark_out`
  - `QProgressDialog` + `QThread` pendant l'export
  - Affichage du poids réel du fichier exporté après complétion

- [ ] Ajouter le bouton "Exporter l'extrait" dans `MainWindow`,
  actif uniquement si une sélection IN/OUT valide existe

### 3.3 Tests et commit

- [ ] Créer `tests/test_export.py` :
  Tests sur `export_clip()` avec fichier vidéo de test (mock ou fichier
  de test inclus dans `tests/fixtures/`)
- [ ] Commit :
  ```bash
  git add .
  git commit -m "feat: add IN/OUT clip selection and export (v0.9.0)"
  git tag -a v0.9.0 -m "Release v0.9.0 — Sélection et export d'extrait"
  git push origin main --tags
  ```

---

## Priorité 4 — Qualité et distribution

**Prérequis :** Priorité 3 complétée ou en parallèle de P2/P3.

- [ ] Compléter la couverture de tests :
  - `tests/test_repair.py` : tests d'intégration `action_repair()`
    (nécessite ffmpeg installé, utiliser `pytest.mark.integration`)
  - `tests/test_convert.py` : tests d'intégration `action_convert_mp4()`
  - `tests/test_export.py` : tests `export_clip()` en mode copy et reencode

- [ ] Ajouter `pytest.ini` ou section `[tool.pytest.ini_options]` dans
  `pyproject.toml` :
  ```toml
  [tool.pytest.ini_options]
  markers = ["integration: tests nécessitant ffmpeg installé"]
  ```

- [ ] Vérifier portabilité : aucun fichier de config écrit hors du dossier
  du projet. PyQt6 peut écrire dans `~/.config` via `QSettings` — forcer
  le scope local :
  ```python
  QSettings(str(CONFIG_PATH / "settings.ini"), QSettings.Format.IniFormat)
  ```
  où `CONFIG_PATH` est un sous-dossier du projet.

- [ ] Nettoyage au démarrage : scanner le dossier source pour les patterns
  `*.repair_tmp.*` et `*.tmp_converting.mp4` orphelins (interruption
  brutale lors d'une session précédente) et proposer leur suppression.

- [ ] Mettre à jour `run.sh` pour supporter aussi le lancement GUI :
  ```bash
  # run.sh --gui lance rusheshour_gui.py
  ```

- [ ] Packaging optionnel (hors scope immédiat, à décider) :
  PyInstaller ou Nuitka pour un binaire autonome sans dépendances Python.

- [ ] Commit final :
  ```bash
  git add .
  git commit -m "chore: tests, portability fixes, cleanup (v1.0.0)"
  git tag -a v1.0.0 -m "Release v1.0.0 — Feature complete"
  git push origin main --tags
  ```

---

## Notes techniques pour Claude Code

### Wayland / X11
mpv embarqué via `wid` fonctionne nativement sous X11. Sous Wayland pur,
`wid` n'est pas supporté. Forcer XWayland au lancement GUI :
```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
```
Documenter cette limitation dans le README. L'environnement cible est
Debian 13 + KDE Plasma.

### Thread safety python-mpv ↔ Qt
Les observers python-mpv (`@player.property_observer`) s'exécutent dans
le thread interne mpv. Toute mise à jour de widget Qt depuis un observer
DOIT passer par un signal Qt (`pyqtSignal`) — jamais directement.
Exemple correct :
```python
class PlayerWidget(QWidget):
    position_changed = pyqtSignal(float)

    def __init__(self):
        self.player = mpv.MPV(...)
        self.player.observe_property("time-pos", self._on_time_pos)

    def _on_time_pos(self, name, value):
        if value is not None:
            self.position_changed.emit(value)  # thread-safe
```

### Progression ffmpeg
ffmpeg écrit sa progression sur stderr. Pour une barre de progression
précise, parser les lignes `frame=... fps=... time=... bitrate=...` :
```python
import re
pattern = re.compile(r"time=(\d+):(\d+):([\d.]+)")
```
Comparer `time` avec la durée totale (ffprobe) pour calculer le
pourcentage.

### Fichiers temporaires
Le script produit `*.repair_tmp.*` et `*.tmp_converting.mp4`. Supprimés
automatiquement en cas de succès ou d'échec ffmpeg. En cas de SIGKILL,
ils subsistent. Prévoir un nettoyage au démarrage (P4).
