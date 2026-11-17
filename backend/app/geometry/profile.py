"""2D analysis of charm profiles: the smallest-feature check of rule CH-03.

A profile passes when no stroke, tip, neck or gap is narrower than the mold limit (0.6 mm).
The check is a morphological opening and closing with a disc of half that width:

- *opening* (shrink, then grow back) removes every part narrower than 0.6 mm: a thin neck
  splits the shape, a thin stroke disappears, a hairline tail loses its area;
- *closing* (grow, then shrink back) fills every gap narrower than 0.6 mm: a narrow counter
  closes, two strokes that almost touch join and enclose a new hole.

Sharp corners also lose (or gain) a little area; the mold maker rounds them with the 0.3 mm
tip radius anyway, so a small area change is tolerated and only larger ones fail. The
analysis uses shapely polygons sampled from the exact CadQuery outlines (OpenCascade's own
2D offset is not reliable on font curves); the model itself stays exact.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopAbs import TopAbs_REVERSED
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.standards.rules import MIN_FEATURE_MM

SAMPLING_TOLERANCE_MM = 0.005
AREA_TOLERANCE = 0.03  # rounding the corners may change the area by up to 3%
_EPS = 1e-3  # keeps features of exactly 0.6 mm on the passing side
_QUAD_SEGS = 8


def _wire_points(wire: cq.Wire) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    explorer = BRepTools_WireExplorer(wire.wrapped)
    while explorer.More():
        edge = explorer.Current()
        curve = BRepAdaptor_Curve(edge)
        sampler = GCPnts_QuasiUniformDeflection(curve, SAMPLING_TOLERANCE_MM)
        segment = [curve.Value(sampler.Parameter(i)) for i in range(1, sampler.NbPoints() + 1)]
        coords = [(p.X(), p.Y()) for p in segment]
        if edge.Orientation() == TopAbs_REVERSED:
            coords.reverse()
        points.extend(coords[:-1])
        explorer.Next()
    return points


def to_polygon(faces: Iterable[cq.Face]) -> BaseGeometry:
    """Planar XY faces as one shapely (Multi)Polygon; overlapping faces are merged."""
    polygons = [
        Polygon(_wire_points(f.outerWire()), [_wire_points(w) for w in f.innerWires()]).buffer(0)
        for f in faces
    ]
    return unary_union(polygons)


def _parts(geom: BaseGeometry) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [] if geom.is_empty else [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


@dataclass(frozen=True)
class FeatureReport:
    """Result of the CH-03 check on one profile."""

    pieces: int
    holes: int
    thin_feature: bool  # some stroke, tip or neck is narrower than the limit
    narrow_gap: bool  # some gap or counter is narrower than the limit
    area_lost: float  # fraction removed by the opening
    area_gained: float  # fraction added by the closing

    @property
    def ok(self) -> bool:
        return not (self.thin_feature or self.narrow_gap)


def check_min_feature(geom: BaseGeometry, min_feature: float = MIN_FEATURE_MM) -> FeatureReport:
    radius = min_feature / 2 - _EPS
    parts = _parts(geom)
    holes = sum(len(p.interiors) for p in parts)
    area = geom.area

    opened = geom.buffer(-radius, quad_segs=_QUAD_SEGS).buffer(radius, quad_segs=_QUAD_SEGS)
    closed = geom.buffer(radius, quad_segs=_QUAD_SEGS).buffer(-radius, quad_segs=_QUAD_SEGS)
    opened_parts, closed_parts = _parts(opened), _parts(closed)
    lost = 1 - opened.area / area if area else 1.0
    gained = closed.area / area - 1 if area else 0.0

    thin = (
        len(opened_parts) != len(parts)
        or sum(len(p.interiors) for p in opened_parts) != holes
        or lost > AREA_TOLERANCE
    )
    narrow = (
        len(closed_parts) != len(parts)
        or sum(len(p.interiors) for p in closed_parts) != holes
        or gained > AREA_TOLERANCE
    )
    return FeatureReport(len(parts), holes, thin, narrow, lost, gained)
