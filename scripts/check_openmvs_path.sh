#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON:-python3}"
if [[ -x ".venv/bin/python" ]]; then
  python_bin=".venv/bin/python"
fi

missing=0
for tool in InterfaceCOLMAP DensifyPointCloud ReconstructMesh RefineMesh TextureMesh; do
  resolved="$("$python_bin" - "$tool" <<'PY'
import sys
from vidtolevel.core.tools import which

print(which(sys.argv[1]) or "")
PY
)"
  if [[ -n "$resolved" ]]; then
    printf 'OK      %-20s %s\n' "$tool" "$resolved"
  else
    printf 'MISSING %-20s\n' "$tool"
    missing=1
  fi
done

exit "$missing"
