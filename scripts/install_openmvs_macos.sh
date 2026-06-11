#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This helper installs the official OpenMVS macOS arm64 prebuilt release." >&2
  echo "For other platforms, install OpenMVS manually and set VIDTOLEVEL_OPENMVS_BIN." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip is required." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to parse the GitHub release metadata." >&2
  exit 1
fi

install_dir="${1:-${VIDTOLEVEL_OPENMVS_DIR:-$(pwd)/.tools/openmvs}}"
bin_dir="$install_dir/bin"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

if [[ -n "${OPENMVS_URL:-}" ]]; then
  asset_url="$OPENMVS_URL"
  tag="${OPENMVS_VERSION:-custom}"
else
  if [[ "${OPENMVS_VERSION:-latest}" == "latest" ]]; then
    release_url="https://api.github.com/repos/cdcseacave/openMVS/releases/latest"
  else
    release_url="https://api.github.com/repos/cdcseacave/openMVS/releases/tags/${OPENMVS_VERSION}"
  fi

  release_json="$tmp_dir/release.json"
  curl -fsSL "$release_url" -o "$release_json"
  tag="$(python3 - "$release_json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["tag_name"])
PY
)"
  asset_url="$(python3 - "$release_json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for asset in data.get("assets", []):
    if asset.get("name") == "OpenMVS_macOS_arm64.zip":
        print(asset["browser_download_url"])
        break
else:
    raise SystemExit("OpenMVS_macOS_arm64.zip was not found in this release.")
PY
)"
fi

archive="$tmp_dir/OpenMVS_macOS_arm64.zip"
echo "Downloading OpenMVS ${tag}..."
curl -L --fail --progress-bar "$asset_url" -o "$archive"

rm -rf "$bin_dir"
mkdir -p "$bin_dir"
unzip -q "$archive" -d "$bin_dir"

required_tools=(
  InterfaceCOLMAP
  DensifyPointCloud
  ReconstructMesh
  RefineMesh
  TextureMesh
)

missing=0
for tool in "${required_tools[@]}"; do
  if [[ -f "$bin_dir/$tool" ]]; then
    chmod +x "$bin_dir/$tool"
  else
    echo "Missing $tool in downloaded OpenMVS archive." >&2
    missing=1
  fi
done

if [[ "$missing" != "0" ]]; then
  exit 1
fi

cat <<EOF
Installed OpenMVS ${tag} to:
  $bin_dir

VidToLevel will discover this location automatically when run from this repo.
From another working directory, export:
  export VIDTOLEVEL_OPENMVS_BIN="$bin_dir"
EOF
