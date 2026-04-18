# Changelog

Tous les changements notables de ce projet sont documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Versionnage Sémantique](https://semver.org/lang/fr/).

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
