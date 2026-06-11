# Installation Notes

## Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
vidtolevel doctor
```

The CLI is intentionally import-light: `vidtolevel --help` and `vidtolevel
doctor` work before OpenCV/FastAPI/Numpy are installed. Frame filtering, the API
server, and the viewer need the dependencies from `pyproject.toml`.

## External Binaries

VidToLevel calls these binaries from `PATH`:

- `ffmpeg`
- `colmap`
- `InterfaceCOLMAP`
- `DensifyPointCloud`
- `ReconstructMesh`
- `RefineMesh`
- `TextureMesh`
- `blender`

Run:

```bash
vidtolevel doctor
```

The command exits with code `1` until every required binary is available. That is
expected on a fresh machine.

On macOS with Homebrew, this helper installs the packages Homebrew can provide:

```bash
bash scripts/install_macos_tools.sh
```

The macOS helper also downloads the official OpenMVS macOS arm64 prebuilt
release into `.tools/openmvs/bin` unless `SKIP_OPENMVS=1` is set. To install
only OpenMVS:

```bash
bash scripts/install_openmvs_macos.sh
```

VidToLevel discovers `.tools/openmvs/bin` automatically when commands are run
from this repository. From another working directory, set:

```bash
export VIDTOLEVEL_OPENMVS_BIN="/absolute/path/to/openmvs/bin"
```

After placing the OpenMVS binaries on `PATH`, in `.tools/openmvs/bin`, or in
`VIDTOLEVEL_OPENMVS_BIN`, verify them with:

```bash
bash scripts/check_openmvs_path.sh
```

Current local note: Homebrew's COLMAP package on this Mac reports `without
CUDA`. That is enough for CPU smoke tests here, but the Phase 0 CUDA check must
be repeated on the RTX 4070 Super machine with a CUDA-enabled COLMAP build.

## Smoke Test

After the external tools are installed:

```bash
vidtolevel process /path/to/short_test.mp4 --fps 1 --skip-optimize
```

Then inspect:

```bash
vidtolevel status
vidtolevel viewer runs --no-open
```

For project scanning:

```bash
vidtolevel init-project projects/test_block
vidtolevel add-session /path/to/short_test.mp4 --project projects/test_block --fps 1 --skip-optimize
vidtolevel coverage --project projects/test_block
```
