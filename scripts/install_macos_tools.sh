#!/usr/bin/env bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi

brew install ffmpeg colmap

if ! command -v blender >/dev/null 2>&1; then
  brew install --cask blender
fi

if [[ "${SKIP_OPENMVS:-0}" != "1" ]]; then
  bash "$(dirname "$0")/install_openmvs_macos.sh"
fi

vidtolevel doctor
