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

cat <<'EOF'

OpenMVS is not available as a standard Homebrew formula on this machine.
Install or build OpenMVS separately, then make these binaries available on PATH:

  InterfaceCOLMAP
  DensifyPointCloud
  ReconstructMesh
  RefineMesh
  TextureMesh

After installing OpenMVS, run:

  vidtolevel doctor

EOF

