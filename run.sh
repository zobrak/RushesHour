#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --gui : délègue à run_gui.sh (gestion dépendances système + lancement Qt)
for arg in "$@"; do
    if [ "$arg" = "--gui" ]; then
        shift_args=()
        for a in "$@"; do [ "$a" = "--gui" ] || shift_args+=("$a"); done
        exec "$DIR/run_gui.sh" "${shift_args[@]}"
    fi
done

VENV="$DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo "[RushesHour] Création du venv..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$DIR/requirements.txt"
fi
exec "$VENV/bin/python" "$DIR/sort_rush.py" "$@"
