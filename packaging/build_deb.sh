#!/usr/bin/env bash
# Construit le paquet .deb pour RushesHour (Debian 13+ amd64).
#
# Prérequis : fakeroot, dpkg-deb (inclus dans dpkg)
#   sudo apt install fakeroot
#
# Usage   : bash packaging/build_deb.sh
# Produit : dist/rusheshour_<version>_amd64.deb
#
# Le paquet déclare python3-pyqt6, python3-mpv, libmpv2 et ffmpeg
# comme dépendances apt — ils sont installés automatiquement par apt.
# Il n'embarque PAS ces bibliothèques système.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."

# ── version ────────────────────────────────────────────────────────────────
VERSION=$(python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from rusheshour import __version__
print(__version__)
")

PKGNAME="rusheshour_${VERSION}_amd64"
BUILDDIR="$ROOT/dist/deb/$PKGNAME"
DEB_OUT="$ROOT/dist/rusheshour_${VERSION}_amd64.deb"

echo "[deb] Version    : $VERSION"
echo "[deb] Build dir  : $BUILDDIR"
echo "[deb] Cible      : $DEB_OUT"
echo ""

# ── nettoyage ──────────────────────────────────────────────────────────────
rm -rf "$BUILDDIR"
mkdir -p \
    "$BUILDDIR/DEBIAN" \
    "$BUILDDIR/usr/bin" \
    "$BUILDDIR/usr/lib/python3/dist-packages" \
    "$ROOT/dist"

# ── DEBIAN/control ─────────────────────────────────────────────────────────
cat > "$BUILDDIR/DEBIAN/control" <<EOF
Package: rusheshour
Version: $VERSION
Architecture: amd64
Maintainer: Zobrak <claude@zobrak.net>
Depends: python3 (>= 3.11), python3-pyqt6 (>= 6.4), python3-mpv, libmpv2, ffmpeg
Recommends: kdialog | zenity
Section: video
Priority: optional
Homepage: https://github.com/zobrak/RushesHour
Description: Outil de tri interactif de rush vidéo (CLI + GUI PyQt6)
 RushesHour parcourt récursivement un dossier de rushes vidéo,
 lit chaque fichier via mpv, détecte et répare les fichiers corrompus
 (ffmpeg), et propose un ensemble d'actions : passer au suivant,
 renommer, déplacer, supprimer, convertir en MP4, ou exporter un
 segment IN/OUT par stream copy.
 .
 Ce paquet fournit les commandes rusheshour-gui (interface PyQt6)
 et sort-rush (interface CLI interactive).
EOF

# ── package Python ─────────────────────────────────────────────────────────
cp -r "$ROOT/rusheshour" "$BUILDDIR/usr/lib/python3/dist-packages/"

# Supprimer artefacts inutiles/sensibles
find "$BUILDDIR/usr/lib/python3/dist-packages/rusheshour" \
    \( -name "__pycache__" -type d \
    -o -name "*.pyc" \
    -o -name ".claude" -type d \) \
    -exec rm -rf {} + 2>/dev/null || true

# Permissions standard Debian : dirs 755, fichiers 644
find "$BUILDDIR/usr" -type d -exec chmod 755 {} +
find "$BUILDDIR/usr/lib" -type f -exec chmod 644 {} +

# ── points d'entrée ────────────────────────────────────────────────────────
cat > "$BUILDDIR/usr/bin/rusheshour-gui" <<'PYEOF'
#!/usr/bin/python3
import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
from rusheshour.gui import launch_gui
if __name__ == "__main__":
    launch_gui()
PYEOF

cat > "$BUILDDIR/usr/bin/sort-rush" <<'PYEOF'
#!/usr/bin/python3
from rusheshour.cli.main import main
if __name__ == "__main__":
    main()
PYEOF

chmod 755 \
    "$BUILDDIR/usr/bin/rusheshour-gui" \
    "$BUILDDIR/usr/bin/sort-rush"

# dpkg-deb exige DEBIAN/ en 0755
chmod 755 "$BUILDDIR/DEBIAN"

# ── build ──────────────────────────────────────────────────────────────────
fakeroot dpkg-deb --build --root-owner-group "$BUILDDIR" "$DEB_OUT"

echo ""
echo "[deb] ✓ Paquet produit : $DEB_OUT"
dpkg-deb --info "$DEB_OUT" | grep -E "(Package|Version|Architecture|Depends|Size)"
echo ""
echo "[deb] Installer avec :"
echo "        sudo apt install \"$DEB_OUT\""
echo "  ou   sudo dpkg -i \"$DEB_OUT\" && sudo apt install -f"
