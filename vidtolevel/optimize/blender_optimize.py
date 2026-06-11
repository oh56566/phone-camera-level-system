from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-faces", type=int, default=500_000)
    parser.add_argument("--collision-mode", choices=["ground-slab", "bounds", "none"], default="ground-slab")
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_mesh(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.context.scene.objects)
    suffix = path.suffix.lower()
    if suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        raise ValueError(f"Unsupported mesh input: {path}")
    imported = [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"No mesh objects imported from {path}")
    return imported


def join_meshes(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    active = bpy.context.object
    active.name = name
    active.data.name = f"{name}_Mesh"
    return active


def face_count(obj: bpy.types.Object) -> int:
    return len(obj.data.polygons)


def decimate_to_target(obj: bpy.types.Object, target_faces: int) -> None:
    current_faces = face_count(obj)
    if current_faces <= target_faces or current_faces == 0:
        return
    ratio = max(0.01, min(1.0, target_faces / current_faces))
    modifier = obj.modifiers.new(name="VTL_Decimate", type="DECIMATE")
    modifier.ratio = ratio
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def create_bounds_collision(source: bpy.types.Object) -> bpy.types.Object:
    world_corners = [source.matrix_world @ Vector(corner) for corner in source.bound_box]
    min_corner = Vector((min(v.x for v in world_corners), min(v.y for v in world_corners), min(v.z for v in world_corners)))
    max_corner = Vector((max(v.x for v in world_corners), max(v.y for v in world_corners), max(v.z for v in world_corners)))
    center = (min_corner + max_corner) * 0.5
    dimensions = max_corner - min_corner

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    collision = bpy.context.object
    collision.name = f"UCX_{source.name}_00"
    collision.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    collision.display_type = "WIRE"
    return collision


def create_ground_slab_collision(source: bpy.types.Object) -> bpy.types.Object:
    world_corners = [source.matrix_world @ Vector(corner) for corner in source.bound_box]
    min_corner = Vector((min(v.x for v in world_corners), min(v.y for v in world_corners), min(v.z for v in world_corners)))
    max_corner = Vector((max(v.x for v in world_corners), max(v.y for v in world_corners), max(v.z for v in world_corners)))
    dimensions = max_corner - min_corner
    thickness = max(dimensions.z * 0.02, 0.05)
    center = Vector(
        (
            (min_corner.x + max_corner.x) * 0.5,
            (min_corner.y + max_corner.y) * 0.5,
            min_corner.z + thickness * 0.5,
        )
    )

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    collision = bpy.context.object
    collision.name = f"UCX_{source.name}_Ground_00"
    collision.dimensions = (max(dimensions.x, 0.05), max(dimensions.y, 0.05), thickness)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    collision.display_type = "WIRE"
    return collision


def export_fbx(output_path: Path, objects: list[bpy.types.Object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=str(output_path),
        use_selection=True,
        apply_unit_scale=True,
        bake_space_transform=False,
        object_types={"MESH"},
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
    )


def main() -> int:
    args = parse_args()
    clear_scene()
    visual = join_meshes(import_mesh(Path(args.input)), "VTL_Scan")
    decimate_to_target(visual, args.target_faces)

    bpy.ops.object.select_all(action="DESELECT")
    visual.select_set(True)
    bpy.context.view_layer.objects.active = visual
    bpy.ops.object.shade_smooth()

    export_objects = [visual]
    if args.collision_mode == "ground-slab":
        export_objects.append(create_ground_slab_collision(visual))
    elif args.collision_mode == "bounds":
        export_objects.append(create_bounds_collision(visual))

    export_fbx(Path(args.output), export_objects)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
