#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="1.0.0"

if [[ ! -r /etc/os-release ]]; then
  echo "This package must be built on Ubuntu." >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "DashboardAPI-EC .deb builds are supported only on Ubuntu." >&2
  exit 1
fi

for command in dpkg-deb python3 npm; do
  command -v "$command" >/dev/null || { echo "Missing build dependency: $command" >&2; exit 1; }
done

ARCH="$(dpkg --print-architecture)"
BUILD_DIR="$(mktemp -d)"
STAGE="$BUILD_DIR/dashboardapi-ec_${VERSION}_${ARCH}"
trap 'rm -rf "$BUILD_DIR"' EXIT

mkdir -p "$STAGE/DEBIAN" \
  "$STAGE/opt/dashboardapi-ec/backend" \
  "$STAGE/opt/dashboardapi-ec/wheels" \
  "$STAGE/usr/share/dashboardapi-ec/frontend" \
  "$STAGE/lib/systemd/system" \
  "$STAGE/etc/nginx/sites-available"

sed -e "s/@VERSION@/$VERSION/g" -e "s/@ARCH@/$ARCH/g" "$ROOT_DIR/packaging/debian/control" > "$STAGE/DEBIAN/control"
install -m 0755 "$ROOT_DIR/packaging/debian/preinst" "$STAGE/DEBIAN/preinst"
install -m 0755 "$ROOT_DIR/packaging/debian/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$ROOT_DIR/packaging/debian/prerm" "$STAGE/DEBIAN/prerm"

python3 -m pip wheel --wheel-dir "$STAGE/opt/dashboardapi-ec/wheels" "$ROOT_DIR/backend"
cp -a "$ROOT_DIR/backend/alembic" "$STAGE/opt/dashboardapi-ec/backend/"
cp -a "$ROOT_DIR/backend/app" "$STAGE/opt/dashboardapi-ec/backend/"
cp "$ROOT_DIR/backend/alembic.ini" "$STAGE/opt/dashboardapi-ec/backend/"

cd "$ROOT_DIR/frontend"
if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
npm run build
cp -a dist/. "$STAGE/usr/share/dashboardapi-ec/frontend/"

install -m 0644 "$ROOT_DIR/packaging/systemd/dashboardapi-ec.service" "$STAGE/lib/systemd/system/"
install -m 0644 "$ROOT_DIR/packaging/systemd/dashboardapi-ec-worker.service" "$STAGE/lib/systemd/system/"
install -m 0644 "$ROOT_DIR/packaging/nginx/dashboardapi-ec.conf" "$STAGE/etc/nginx/sites-available/dashboardapi-ec"

mkdir -p "$ROOT_DIR/dist"
dpkg-deb --build --root-owner-group "$STAGE" "$ROOT_DIR/dist/dashboardapi-ec_${VERSION}_${ARCH}.deb"
echo "Created dist/dashboardapi-ec_${VERSION}_${ARCH}.deb"
