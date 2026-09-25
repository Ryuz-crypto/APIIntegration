#!/usr/bin/env bash
set -euo pipefail

BUILD_STAGE="initialization"
trap 'status=$?; echo "::error title=DashboardAPI-EC package build::${BUILD_STAGE} failed at line ${LINENO}" >&2; exit "$status"' ERR

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_VERSION="1.0.0"

if [[ ! -r /etc/os-release ]]; then
  echo "This package must be built on Ubuntu." >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "DashboardAPI-EC .deb builds require Ubuntu with Python 3.12 or newer." >&2
  echo "Detected system: ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

for command in dpkg-deb python3 npm; do
  command -v "$command" >/dev/null || { echo "Missing build dependency: $command" >&2; exit 1; }
done

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
  echo "DashboardAPI-EC .deb builds require Python 3.12 or newer; detected: $(python3 --version)." >&2
  exit 1
fi

ARCH="$(dpkg --print-architecture)"
BUILD_DIR="$(mktemp -d)"
STAGE="$BUILD_DIR/dashboardapi-ec_${PACKAGE_VERSION}_${ARCH}"
trap 'rm -rf "$BUILD_DIR"' EXIT

mkdir -p "$STAGE/DEBIAN" \
  "$STAGE/opt/dashboardapi-ec/backend" \
  "$STAGE/opt/dashboardapi-ec/wheels" \
  "$STAGE/usr/share/dashboardapi-ec/frontend" \
  "$STAGE/lib/systemd/system" \
  "$STAGE/etc/nginx/sites-available"

sed -e "s/@VERSION@/$PACKAGE_VERSION/g" -e "s/@ARCH@/$ARCH/g" "$ROOT_DIR/packaging/debian/control" > "$STAGE/DEBIAN/control"
install -m 0755 "$ROOT_DIR/packaging/debian/preinst" "$STAGE/DEBIAN/preinst"
install -m 0755 "$ROOT_DIR/packaging/debian/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$ROOT_DIR/packaging/debian/prerm" "$STAGE/DEBIAN/prerm"

BUILD_STAGE="Python wheel build"
python3 -m pip wheel --wheel-dir "$STAGE/opt/dashboardapi-ec/wheels" "$ROOT_DIR/backend"
cp -a "$ROOT_DIR/backend/alembic" "$STAGE/opt/dashboardapi-ec/backend/"
cp -a "$ROOT_DIR/backend/app" "$STAGE/opt/dashboardapi-ec/backend/"
cp "$ROOT_DIR/backend/alembic.ini" "$STAGE/opt/dashboardapi-ec/backend/"

cd "$ROOT_DIR/frontend"
BUILD_STAGE="frontend dependency installation"
if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
BUILD_STAGE="frontend production build"
npm run build
cp -a dist/. "$STAGE/usr/share/dashboardapi-ec/frontend/"

install -m 0644 "$ROOT_DIR/packaging/systemd/dashboardapi-ec.service" "$STAGE/lib/systemd/system/"
install -m 0644 "$ROOT_DIR/packaging/systemd/dashboardapi-ec-worker.service" "$STAGE/lib/systemd/system/"
install -m 0644 "$ROOT_DIR/packaging/nginx/dashboardapi-ec.conf" "$STAGE/opt/dashboardapi-ec/nginx-http.conf"
install -m 0644 "$ROOT_DIR/packaging/nginx/bootstrap.conf" "$STAGE/opt/dashboardapi-ec/nginx-bootstrap.conf"
install -m 0644 "$ROOT_DIR/packaging/systemd/dashboardapi-ec-tls.service" "$STAGE/lib/systemd/system/"
install -m 0644 "$ROOT_DIR/packaging/systemd/dashboardapi-ec-tls.timer" "$STAGE/lib/systemd/system/"
install -m 0755 "$ROOT_DIR/scripts/apply-tls.py" "$STAGE/opt/dashboardapi-ec/apply-tls.py"
install -m 0644 "$ROOT_DIR/../LICENSE" "$STAGE/usr/share/dashboardapi-ec/LICENSE"

mkdir -p "$ROOT_DIR/dist"
BUILD_STAGE="Debian archive assembly"
if ! DPKG_OUTPUT="$(dpkg-deb --root-owner-group --build "$STAGE" "$ROOT_DIR/dist/dashboardapi-ec_${PACKAGE_VERSION}_${ARCH}.deb" 2>&1)"; then
  echo "$DPKG_OUTPUT" >&2
  ANNOTATION="${DPKG_OUTPUT//'%'/'%25'}"
  ANNOTATION="${ANNOTATION//$'\r'/'%0D'}"
  ANNOTATION="${ANNOTATION//$'\n'/'%0A'}"
  echo "::error title=Debian archive assembly::${ANNOTATION}" >&2
  exit 2
fi
echo "$DPKG_OUTPUT"
echo "Created dist/dashboardapi-ec_${PACKAGE_VERSION}_${ARCH}.deb"
