"""Measurements (volume, mass, bounding box) and file exports (STEP, STL, GLB)."""

from dataclasses import asdict, dataclass
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

from app.core.content import materials

LINEAR_TOLERANCE_MM = 0.01
ANGULAR_TOLERANCE_RAD = 0.2


@dataclass(frozen=True)
class Measurements:
    volume_mm3: float
    mass_g: float
    material: str
    density_g_cm3: float
    bbox_mm: tuple[float, float, float]

    def to_dict(self) -> dict:
        return asdict(self)


def measure(shape: cq.Shape, material: str) -> Measurements:
    """Volume from the exact B-rep; mass before plating (manual 01-overview)."""
    density = materials()[material]["density_g_cm3"]
    volume = shape.Volume()
    box = shape.BoundingBox()
    return Measurements(
        volume_mm3=round(volume, 2),
        mass_g=round(volume / 1000 * density, 3),
        material=material,
        density_g_cm3=density,
        bbox_mm=(round(box.xlen, 2), round(box.ylen, 2), round(box.zlen, 2)),
    )


def to_mesh(shape: cq.Shape) -> trimesh.Trimesh:
    """Triangle mesh in millimetres. Vertices are not shared between CAD faces, so sharp
    edges (facets, charm sides) stay sharp when the viewer computes normals."""
    vertices, triangles = shape.tessellate(LINEAR_TOLERANCE_MM, ANGULAR_TOLERANCE_RAD)
    return trimesh.Trimesh(
        vertices=np.array([v.toTuple() for v in vertices]),
        faces=np.array(triangles),
        process=False,
    )


def export_step(shape: cq.Shape, path: Path) -> None:
    cq.exporters.export(shape, str(path), exportType="STEP")


def export_stl(shape: cq.Shape, path: Path) -> None:
    cq.exporters.export(
        shape,
        str(path),
        exportType="STL",
        tolerance=LINEAR_TOLERANCE_MM,
        angularTolerance=ANGULAR_TOLERANCE_RAD,
    )


def glb_bytes(shape: cq.Shape) -> bytes:
    """Binary glTF in metres (the glTF unit), Y up as glTF expects: model Z becomes Y."""
    mesh = to_mesh(shape)
    mesh.apply_scale(0.001)
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    return trimesh.Scene(mesh).export(file_type="glb")


def export_glb(shape: cq.Shape, path: Path) -> None:
    path.write_bytes(glb_bytes(shape))
