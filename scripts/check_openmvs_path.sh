#!/usr/bin/env bash
set -euo pipefail

missing=0
for tool in InterfaceCOLMAP DensifyPointCloud ReconstructMesh RefineMesh TextureMesh; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf 'OK      %-20s %s\n' "$tool" "$(command -v "$tool")"
  else
    printf 'MISSING %-20s\n' "$tool"
    missing=1
  fi
done

exit "$missing"

