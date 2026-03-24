#!/usr/bin/env bash
set -euo pipefail

# Bootstrap local dev tools for qa-mail-ingest on Ubuntu/Debian-like systems.
#
# Installs:
# - OS packages needed for development
# - nvm
# - latest Node LTS
# - uv
# - Python 3.12 via uv
# - local .venv
# - local Wrangler dev dependency
#
# After running, you still need to manually create/export:
# - CF_API_TOKEN
# - CF_ACCOUNT_ID
# - CF_ZONE_ID

PROJECT_DIR="${1:-$PWD}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
NVM_VERSION="${NVM_VERSION:-v0.40.3}"
BASHRC="${HOME}/.bashrc"

echo "==> Checking apt health"
if ! sudo apt-get update; then
  cat >&2 <<'EOF'
apt-get update failed.

Your system likely has a broken or stale apt repository configured.
Please fix that first, then rerun this script.

You can inspect configured repositories with:
  grep -R "^[^#].*deb " /etc/apt/sources.list /etc/apt/sources.list.d/*

EOF
  exit 1
fi

echo "==> Installing OS packages"
sudo apt-get install -y \
  curl \
  ca-certificates \
  git \
  build-essential \
  unzip

echo "==> Installing nvm"
export NVM_DIR="${HOME}/.nvm"
if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
  curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
fi

echo "==> Ensuring future shells load nvm"
if ! grep -Fq 'export NVM_DIR="$HOME/.nvm"' "${BASHRC}" 2>/dev/null; then
  cat >> "${BASHRC}" <<'EOF'

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
EOF
fi

echo "==> Installing latest Node LTS"
set +u
# shellcheck disable=SC1090
source "${NVM_DIR}/nvm.sh"
nvm install --lts
nvm use --lts
set -u

echo "==> Verifying Node toolchain"
node --version
npm --version
npx --version

echo "==> Installing uv"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

echo "==> Verifying uv"
uv --version

echo "==> Installing Python ${PYTHON_VERSION} via uv"
uv python install "${PYTHON_VERSION}"

echo "==> Preparing project dir: ${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}"
cd "${PROJECT_DIR}"

if [[ ! -f package.json ]]; then
  echo "==> Creating package.json"
  npm init -y >/dev/null
fi

echo "==> Installing Wrangler locally"
npm install --save-dev wrangler

echo "==> Verifying Wrangler"
npx wrangler --version

if [[ ! -f pyproject.toml ]]; then
  echo "==> Creating minimal pyproject.toml"
  cat > pyproject.toml <<'EOF'
[project]
name = "qa-mail-ingest"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[tool.uv]
EOF
fi

if [[ ! -d .venv ]]; then
  echo "==> Creating .venv"
  uv venv --python "${PYTHON_VERSION}"
fi

echo "==> Installing basic Python dev tools into .venv"
uv pip install --python .venv/bin/python \
  pytest \
  ruff

cat <<EOF

==> Done.

Useful next steps:

1. Reload your shell so nvm is available automatically
   source "${BASHRC}"

2. Activate Python env
   source "${PROJECT_DIR}/.venv/bin/activate"

3. Check Wrangler again
   cd "${PROJECT_DIR}"
   npx wrangler --version

4. Authenticate Wrangler later however you prefer
   npx wrangler login
   or export CLOUDFLARE_API_TOKEN=...

5. Export Cloudflare values after you create them manually
   export CF_API_TOKEN='...'
   export CF_ACCOUNT_ID='...'
   export CF_ZONE_ID='...'
EOF
