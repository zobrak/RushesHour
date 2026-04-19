# Installation — RushesHour

## Prérequis système (toutes méthodes)

| Outil | Rôle | Debian / Ubuntu |
|-------|------|-----------------|
| `libmpv2` + `mpv` | Lecture vidéo embarquée | `sudo apt install mpv libmpv2` |
| `ffmpeg` (inclut `ffprobe`) | Encodage, réparation, export | `sudo apt install ffmpeg` |
| Python 3.11+ | Interpréteur | `sudo apt install python3` |

---

## Méthode 1 — Paquet .deb (Debian 13 Trixie, recommandé)

Installe `rusheshour-gui` et `sort-rush` dans `/usr/bin/`. Les dépendances Python
(`python3-pyqt6`, `python3-mpv`) sont installées automatiquement par apt.

```bash
# Télécharger le .deb depuis GitHub Releases, puis :
sudo apt install ./rusheshour_1.0.0_amd64.deb

# Lancement
rusheshour-gui [dossier]
sort-rush [options] <dossier>
```

> `python3-mpv` 1.0.7 est disponible dans Trixie/main depuis Debian 13.
> Sur Debian 12 (Bookworm) et versions antérieures, utiliser la Méthode 2.

---

## Méthode 2 — Scripts de bootstrap (Linux, recommandé hors Debian 13)

Clone le dépôt et crée automatiquement un venv Python isolé dans `.venv/`.
`run_gui.sh` vérifie la présence de `libmpv2` et `ffmpeg` avant de lancer.

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour

# GUI (vérifie les dépendances système, crée le venv, lance)
bash run_gui.sh [dossier]

# CLI
bash run.sh [dossier]

# GUI via run.sh
bash run.sh --gui [dossier]
```

**Dépendances Python installées automatiquement dans le venv :**
- `PyQt6 >= 6.4`
- `python-mpv >= 1.0.0`

---

## Méthode 3 — Mode développement (pip install -e)

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour

# Créer et activer un venv
python3 -m venv .venv
source .venv/bin/activate

# Installer en mode éditable avec dépendances GUI
pip install -e ".[gui]"

# Dépendances de développement (tests)
pip install -r requirements-dev.txt

# Lancement
python rusheshour_gui.py [dossier]
python sort_rush.py [options] <dossier>
```

---

## Méthode 4 — Construire le .deb depuis les sources

```bash
git clone https://github.com/zobrak/RushesHour.git
cd RushesHour

# Prérequis : fakeroot
sudo apt install fakeroot

bash packaging/build_deb.sh
# → dist/rusheshour_1.0.0_amd64.deb

sudo apt install ./dist/rusheshour_1.0.0_amd64.deb
```

---

## Dépannage

### `libmpv.so.2` introuvable

```bash
sudo apt install libmpv2
```

Si la bibliothèque est installée mais non trouvée :

```bash
ldconfig -p | grep mpv
sudo ldconfig
```

### Erreur `xcb` au démarrage de la GUI

```bash
sudo apt install libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1
```

### Pas d'affichage vidéo (écran noir)

Vérifier que le GPU supporte OpenGL 3.3+ :

```bash
glxinfo | grep "OpenGL version"
```

RushesHour utilise `MpvRenderContext` (rendu OpenGL dans `QOpenGLWidget`) —
pas de fallback logiciel.

### GUI lente au démarrage

Normal : le premier lancement crée le venv et installe les dépendances Python.
Les lancements suivants démarrent directement.

---

## Autres plateformes (à venir — P5)

| Plateforme | Format | État |
|------------|--------|------|
| Linux cross-distro | AppImage | 🔲 Planifié |
| Windows 10+ | PyInstaller (.exe) | 🔲 Planifié |
| Toute distro (store) | Flatpak / Flathub | 🔲 Planifié |

Voir [TODO.md](TODO.md) pour le détail des prérequis et l'ordre de priorité.
