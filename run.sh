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
