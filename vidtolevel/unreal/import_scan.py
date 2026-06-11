from __future__ import annotations

import argparse
from pathlib import Path

import unreal


def import_fbx(fbx_path: Path, destination: str) -> unreal.Object:
    task = unreal.AssetImportTask()
    task.filename = str(fbx_path)
    task.destination_path = destination
    task.automated = True
    task.replace_existing = True
    task.save = True

    options = unreal.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.static_mesh_import_data.combine_meshes = False
    options.static_mesh_import_data.auto_generate_collision = False
    task.options = options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    if not task.imported_object_paths:
        raise RuntimeError(f"No asset imported from {fbx_path}")
    return unreal.load_asset(task.imported_object_paths[0])


def enable_nanite(asset: unreal.Object) -> None:
    if not isinstance(asset, unreal.StaticMesh):
        return
    try:
        unreal.StaticMeshEditorSubsystem().set_nanite_enabled(asset, True)
    except Exception:
        unreal.log_warning(f"Nanite enable failed for {asset.get_name()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True)
    parser.add_argument("--destination", default="/Game/VidToLevel/Scans")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asset = import_fbx(Path(args.fbx), args.destination)
    enable_nanite(asset)
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    unreal.log(f"Imported VidToLevel scan: {asset.get_path_name()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

