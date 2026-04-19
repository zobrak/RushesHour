# Changelog

Tous les changements notables de ce projet sont documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Versionnage Sémantique](https://semver.org/lang/fr/).

---

## [0.9.5] — Proposition de conversion MP4 au passage au suivant

### Ajouté
- `gui/main_window.py` — `_act_next()` : si `opt_convert` est activé et que le
  fichier courant n'est pas déjà en MP4/H.264 (info chargée, sans erreur),
  une boîte de dialogue demande « Convertir avant de passer au suivant ? »
  — [Oui] lance `ConvertDialog` puis passe au suivant si la conversion réussit ;
  [Non] passe au suivant sans conversion ; [Annuler] reste sur le fichier.

### Corrigé
- `gui/main_window.py` — `_act_move()` : remplace `QFileDialog.getExistingDirectory`
  par `_pick_directory()` (même correction que v0.9.4, chemin manqué).

---

## [0.9.4] — Correctif sélecteur de dossier : processus externe (kdialog/zenity)

### Corrigé
- `gui/main_window.py` — `_open_folder_dialog()` et `_set_destination_dialog()` :
  remplacés par `_pick_directory()` qui appelle `kdialog` (KDE) ou `zenity` (GTK)
  via `subprocess.run`. Sous XCB + QOpenGLWidget + mpv, `QFileDialog` (natif ou
  non-natif) provoque un SIGABRT : Qt tente de créer une fenêtre XCB native alors
  que le contexte OpenGL mpv est actif, ce qui abort le processus. Déléguer à un
  processus externe élimine toute interaction avec le contexte OpenGL.

---

## [0.9.3] — Correctif QFileDialog portal hang (XCB/Wayland) [incomplet]

### Corrigé
- `gui/main_window.py` — `_open_folder_dialog()` et `_set_destination_dialog()` :
  ajout de `QFileDialog.Option.DontUseNativeDialog`. Sans cette option, Qt tente
  d'utiliser xdg-desktop-portal via D-Bus pour afficher le sélecteur natif KDE ;
  sous XCB (app forcée en `QT_QPA_PLATFORM=xcb` sur compositeur Wayland), le
  portal essaie de reparenter la fenêtre native de Wayland vers une fenêtre X11 —
  cette opération ne retourne jamais, la boucle d'événements imbriquée tourne à
  vide, la mémoire RAM se remplit jusqu'à saturation et aucun dialogue n'apparaît.

---

## [0.9.2] — Prévention flooding événements mpv

### Corrigé
- `gui/player_widget.py` — `_on_mpv_update()` : ajout du flag `_update_pending`
  pour dédupliquer les appels depuis le thread mpv. Sans ce flag, mpv postait
  un `QEvent` à chaque frame sans attendre que Qt consomme le précédent,
  pouvant saturer la queue d'événements Qt lors d'un rendu intensif.

---

## [0.9.1] — Diagnostic dépendances mpv

### Ajouté
- `run_gui.sh` — script de lancement GUI équivalent à `run.sh` : crée/réutilise
  le venv, installe les dépendances Python, vérifie `ffmpeg`, `ffprobe` et
  `libmpv2` avant de lancer et affiche les commandes d'installation manquantes
- `gui/player_widget.py` — `_show_dep_error()` : distingue `ModuleNotFoundError`
  (python-mpv absent → `pip install python-mpv`) et `OSError` (libmpv2 absente →
  `sudo apt install libmpv2`) ; affiche le diagnostic dans la zone vidéo et dans
  le terminal au lieu d'un simple écran noir

### Modifié
- `rusheshour/__init__.py` — version `0.9.1`

---

## [0.9.0] — Rendu OpenGL, plein écran, optimisations

### Ajouté
- `gui/player_widget.py` — rendu vidéo via `MpvRenderContext` + `QOpenGLWidget` :
  mpv rend directement dans le framebuffer Qt, fenêtre ancrée dans l'UI
  (abandon de `wid=` X11 qui ouvrait une fenêtre flottante sous Wayland/XWayland)
- Plein écran natif : `F` / `Escape` / double-clic — masque tous les panneaux
  hors lecteur ; `showFullScreen()` sur la `MainWindow`
- `gui/main_window.py` — `_FileInfoWorker(QThread)` : `get_video_info` + `check_errors`
  hors du thread GUI, plus aucun gel à l'ouverture d'un fichier
- `gui/player_widget.py` — callback `update_cb` mpv thread-safe via
  `QCoreApplication.postEvent` (type d'événement Qt enregistré)
- `gui/__init__.py` — `QSurfaceFormat` OpenGL 3.3 Core configuré avant tout contexte GL

### Modifié
- `gui/main_window.py` — "Définir la destination" déplacé du menu Fichier vers Options
- `gui/main_window.py` — correction race condition dans `_act_convert` / `_act_repair` :
  snapshot de `self._current` avant `dlg.exec()`
- `gui/main_window.py` — visibilité du bouton Convertir synchronisée avec le toggle
  `opt_convert` via `_refresh_action_visibility()`
- `gui/main_window.py` — `closeEvent` annule le `_FileInfoWorker` en cours et appelle `shutdown()`
- `gui/file_panel.py` — `set_current`, `mark_status`, `update_path` passent de O(n) à O(1) ;
  `_rebuild()` réservé à `set_files()`
- `gui/dialogs.py` — `ConvertWorker` : ajout `_abort` / `abort()`, fix zombie process,
  `missing_ok=True` sur unlink du fichier temporaire
- `gui/dialogs.py` — `RepairDialog` / `ConvertDialog` : `closeEvent()` avec déconnexion
  des signaux et abort/wait du worker
- `gui/dialogs.py` — `ConvertDialog._on_finished` : `try/except FileNotFoundError` sur `stat()`
- `cli/menus.py` — suppression de la proposition de conversion dans `[1] Ne rien faire`
- `rusheshour/__init__.py` — version `0.9.0`

### Corrigé
- Processus mpv bloquait la fermeture : `os._exit()` dans `launch_gui()` remplace
  `sys.exit()` pour ne pas attendre le thread d'événements non-daemon python-mpv
- `shutdown()` utilise un graveyard pour éviter le deadlock `__del__` →
  `terminate()` → `_mpv_terminate_destroy()` depuis `closeEvent()`
- `input_default_bindings=False` : la touche `q` ne détruit plus le contexte mpv embarqué

---

## [0.8.0] — GUI PyQt6

### Ajouté
- `rusheshour/gui/main_window.py` — `MainWindow` avec layout 3 panneaux (FilePanel / PlayerWidget / barre d'actions)
- `rusheshour/gui/player_widget.py` — `PlayerWidget` : lecteur mpv embarqué, thread-safe via `pyqtSignal`
- `rusheshour/gui/timeline_widget.py` — `TimelineWidget` : barre de progression cliquable, timecodes, placeholder IN/OUT (P3)
- `rusheshour/gui/file_panel.py` — `FilePanel` : liste des fichiers avec codes couleur (courant / traité / erreur)
- `rusheshour/gui/dialogs.py` — `RepairDialog`, `ConvertDialog` (progression ffmpeg réelle), `DeleteConfirmDialog`
- `rusheshour_gui.py` — point d'entrée GUI (Option A), force `QT_QPA_PLATFORM=xcb` pour Wayland
- Raccourcis clavier : `0–7`, `Espace` (pause), `I`/`O` (mark IN/OUT P3)
- Thème sombre intégré
- Toutes les actions CLI portées dans la GUI (Suivant, Skip, Renommer, Déplacer, Supprimer, Convertir, Réparer)
- Détection d'erreurs au chargement : bouton Réparer mis en évidence si erreurs ffprobe

### Modifié
- `rusheshour/__init__.py` — version `0.8.0`
- `rusheshour_gui.py` — remplace le placeholder par l'appel à `rusheshour.gui.launch_gui()`

---

## [0.7.1] — Refactoring package

### Ajouté
- Structure package Python `rusheshour/` avec sous-modules `core/` et `cli/`
- `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`
- `run.sh` — bootstrap venv portable
- `.gitignore` standard Python + fichiers temporaires RushesHour
- Tests unitaires `tests/test_probe.py` et `tests/test_scanner.py`
- `CHANGELOG.md` (ce fichier)
- `README.md`

### Modifié
- `sort_rush.py` converti en shim CLI d'une ligne
- `rusheshour_gui.py` créé comme placeholder GUI (Priorité 2)

### Corrigé (audit v0.7.0)
- Import `field` inutilisé supprimé
- `filepath.unlink()` conditionné à `filepath.exists()` dans `action_convert_mp4`
- Anti-pattern expression conditionnelle comme statement dans `action_repair`
  remplacé par `if/else` explicite
- `HELP_TEXT` (aide interne [4]) corrigé — décrivait l'ancienne disposition
  `[0]/[1]` inversée depuis v0.7.0
- Textes `HELP_CONVERT` et `HELP_WORKFLOW` mis à jour pour refléter
  `[0] Suivant / [1] Ne rien faire`
- `textwrap.dedent` corrigé dans `build_parser` (indentation première ligne)
- `confirm()` dans `setup_output_dir` aligné sur la convention d'espacement
- `process_video()` propage le `filepath` modifié depuis `show_menu`

---

## [0.7.0]

### Ajouté
- CLI complet via argparse : `--destination`, `--no-repair`, `--no-convert`,
  `--no-menu`, `--version`, `--help-repair`, `--help-convert`, `--help-workflow`

---

## [0.6.0]

### Ajouté
- Menu principal : Commencer / Destination / Options / Aide / Changelog
- Menu options : toggle réparation/conversion (session uniquement)
- Menu fichier : `[m]` retour menu principal
- `Session` dataclass
- `run_session()` extrait de `main()`

---

## [0.5.1]

### Modifié
- Audit et refactoring complet : versioning SemVer corrigé, constantes en tête
  de module, 7 bug fixes, docstrings complètes, `process_video()` extrait,
  `FFMPEG_ENCODE_FLAGS` factorisé

---

## [0.5.0]

### Ajouté
- Bandeau de lancement
- Changelog complet en en-tête du script

---

## [0.4.1]

### Modifié
- Option `[6]` Convertir en MP4 masquée si le fichier est déjà en MP4/H.264
- Proposition de conversion au passage au suivant

---

## [0.4.0]

### Ajouté
- Réparation intégrée au flux principal : `check_errors()` avant chaque
  lecture, proposition de réparer si erreurs détectées

### Modifié
- Refonte menu : `[0]` Suivant (défaut), `[1]` Ne rien faire

---

## [0.3.0]

### Ajouté
- Réparation ffmpeg en 4 stratégies séquentielles : remuxage simple, regen
  timestamps, tolérance aux erreurs, réencodage de sauvetage
- Vérification ffprobe du résultat
- Détection moov atom manquant (non récupérable par ffmpeg)

---

## [0.2.0]

### Ajouté
- Dossier de destination global au lancement (création si absent, exclusion
  du scan si dans l'arborescence source)
- Confirmations o/n avec Entrée = oui par défaut

---

## [0.1.0]

### Ajouté
- Parcours récursif, lecture mpv, infos ffprobe, menu basique
- Conversion MP4 (H.264/AAC)
- Suppression avec confirmation
