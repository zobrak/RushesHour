#!/usr/bin/env bash
# Point d'entrée GUI — RushesHour
# Crée/réutilise le venv, installe les dépendances, lance la GUI.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

# --- dépendances système -----------------------------------------------
MISSING_SYS=()
command -v ffmpeg  &>/dev/null || MISSING_SYS+=("ffmpeg")
command -v ffprobe &>/dev/null || MISSING_SYS+=("ffprobe (paquet ffmpeg)")
python3 -c "import ctypes; ctypes.CDLL('libmpv.so.2')" 2>/dev/null \
    || python3 -c "import ctypes; ctypes.CDLL('libmpv.so.1')" 2>/dev/null \
    || MISSING_SYS+=("libmpv2 (sudo apt install libmpv2)")

if [ ${#MISSING_SYS[@]} -gt 0 ]; then
    echo "[RushesHour] Dépendances système manquantes :"
    for pkg in "${MISSING_SYS[@]}"; do echo "  • $pkg"; done
    echo ""
    echo "  Installer avec : sudo apt install ${MISSING_SYS[*]//[()a-z ]*}"
    echo "  Exemple complet : sudo apt install ffmpeg libmpv2"
    exit 1
fi

# --- venv Python -------------------------------------------------------
if [ ! -d "$VENV" ]; then
    echo "[RushesHour] Création du venv..."
    python3 -m venv "$VENV"
fi

# Toujours s'assurer que les dépendances sont à jour
"$VENV/bin/pip" install -q -r "$DIR/requirements.txt"

# --- lancement ---------------------------------------------------------
exec "$VENV/bin/python" "$DIR/rusheshour_gui.py" "$@"
