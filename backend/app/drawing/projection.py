"""Orthographic projections with hidden-line removal (OpenCascade HLR).

Each view is a projection frame: `direction` points from the part towards the viewer, and
`x_dir` is the view's horizontal axis; the vertical axis is `direction × x_dir`. The result
is a set of 2D polylines in millimetres (u to the right, v up).
"""

from dataclasses import dataclass

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

Polyline = list[tuple[float, float]]
_DEFLECTION_MM = 0.005

# (direction towards the viewer, horizontal axis) per view and product kind.
FRAMES: dict[tuple[str, str], tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    ("glass_bead", "front"): ((0, -1, 0), (1, 0, 0)),  # hole axis (Z) vertical
    ("glass_bead", "top"): ((0, 0, 1), (1, 0, 0)),  # looking down the hole
    ("charm", "front"): ((0, 0, 1), (1, 0, 0)),  # the face, loop up
    ("charm", "side"): ((-1, 0, 0), (0, 0, 1)),  # from the left: thickness horizontal
}


@dataclass
class Projection:
    visible: list[Polyline]
    hidden: list[Polyline]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        points = [pt for line in self.visible + self.hidden for pt in line]
        us, vs = [p[0] for p in points], [p[1] for p in points]
        return min(us), min(vs), max(us), max(vs)


def _polylines(shape) -> list[Polyline]:
    if shape is None or shape.IsNull():
        return []
    lines = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge_s(explorer.Current()))
        sampler = GCPnts_QuasiUniformDeflection(curve, _DEFLECTION_MM)
        if sampler.IsDone() and sampler.NbPoints() >= 2:
            points = [curve.Value(sampler.Parameter(i)) for i in range(1, sampler.NbPoints() + 1)]
            lines.append([(p.X(), p.Y()) for p in points])
        explorer.Next()
    return lines


def project(shape: cq.Shape, kind: str, view: str) -> Projection:
    direction, x_dir = FRAMES[(kind, view)]
    algo = HLRBRep_Algo()
    algo.Add(shape.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*direction), gp_Dir(*x_dir))))
    algo.Update()
    algo.Hide()
    result = HLRBRep_HLRToShape(algo)
    visible = _polylines(result.VCompound()) + _polylines(result.OutLineVCompound())
    hidden = _polylines(result.HCompound()) + _polylines(result.OutLineHCompound())
    return Projection(visible, hidden)
