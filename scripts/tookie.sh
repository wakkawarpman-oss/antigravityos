#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOKIE_DIR="$ROOT_DIR/tools/tookie-osint"
VENV_ACTIVATE="$TOOKIE_DIR/.venv/bin/activate"

if [[ ! -d "$TOOKIE_DIR" ]]; then
  echo "tookie-osint is not installed at: $TOOKIE_DIR"
  echo "Install first: git clone https://github.com/alfredredbird/tookie-osint.git tools/tookie-osint"
  exit 1
fi

if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo "Virtual environment not found: $VENV_ACTIVATE"
  echo "Create it: python3 -m venv $TOOKIE_DIR/.venv && source $TOOKIE_DIR/.venv/bin/activate && pip install -r $TOOKIE_DIR/requirements.txt"
  exit 1
fi

cd "$TOOKIE_DIR"
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"
exec python3 brib.py "$@"
