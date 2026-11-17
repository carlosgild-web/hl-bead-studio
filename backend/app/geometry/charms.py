"""Charm builders (CRS, INI, DSC). Millimetres.

A charm lies in the XY plane: the body spans y = 0 … height (for a disc, its diameter),
centered on x = 0, and its thickness runs from z = 0 to z = thickness. The hanging loop sits
above the body (CH-02); `charm_profile` returns the outline that the CH-03 check analyses.
"""

import math

import cadquery as cq
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.geometry.model import BuiltModel, Dimension
from app.geometry.profile import to_polygon
from app.geometry.text import outline_with_cap_height, outline_with_height, width_per_cap_height
from app.standards.rules import ENGRAVING_FONT, ENGRAVING_TEXT_FIT, TIP_RADIUS_MM

_LOOP_CLEARANCE = 0.3  # metal kept between the loop hole and the body
_ATTACH_BAND = 0.15  # the loop joins a stroke whose top is within 15% of the height
STAR_INNER_RATIO = 0.5
STAR_OVERLAP_MM = 1.0  # how deep the star's left point goes into the crescent band
ENGRAVING_MAX_LETTER_RATIO = 0.35  # letters at most 35% of the disc diameter
ENGRAVING_GAP_RATIO = 0.2  # gap between engraved capitals, per mm of letter height
ENGRAVING_SPACE_RATIO = 0.5  # width of a space, per mm of letter height
ICON_SIZE_RATIO = 0.5  # icons span half the disc diameter


# ---------------------------------------------------------------- shared helpers


def _extrude(faces: list[cq.Face], thickness: float, z0: float = 0.0) -> cq.Shape:
    solids = [
        cq.Solid.extrudeLinear(f.translate(cq.Vector(0, 0, z0)), cq.Vector(0, 0, thickness))
        for f in faces
    ]
    return solids[0].fuse(*solids[1:]).clean() if len(solids) > 1 else solids[0]


def _polygon_face(poly: Polygon) -> cq.Face:
    def wire(coords) -> cq.Wire:
        return cq.Wire.makePolygon([cq.Vector(x, y, 0) for x, y in list(coords)[:-1]], close=True)

    return cq.Face.makeFromWires(
        wire(poly.exterior.coords), [wire(i.coords) for i in poly.interiors]
    )


def _faces_of(geom: BaseGeometry) -> list[cq.Face]:
    polygons = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    return [_polygon_face(p) for p in polygons if not p.is_empty]


def _top_at(body: BaseGeometry, x: float) -> float | None:
    minx, miny, maxx, maxy = body.bounds
    hit = body.intersection(LineString([(x, miny - 1), (x, maxy + 1)]))
    return None if hit.is_empty else hit.bounds[3]


def place_loop(body: BaseGeometry, inner: float, wall: float) -> tuple[float, float, float]:
    """Loop hole center (x, y) and the top of the stroke it joins.

    The loop goes above the highest stroke closest to the body's center line (CH-07: a
    letter like H has no stroke at the top center, so its loop sits above a stem).
    """
    minx, miny, maxx, maxy = body.bounds
    center = (minx + maxx) / 2
    threshold = maxy - _ATTACH_BAND * (maxy - miny)
    steps = int((maxx - minx) / 0.05) + 1
    attach_x, attach_top = center, maxy
    for k in sorted(range(-steps, steps + 1), key=abs):
        x = center + k * 0.05
        top = _top_at(body, x)
        if top is not None and top >= threshold:
            attach_x, attach_top = x, top
            break
    radius = inner / 2
    samples = [attach_x + radius * (i / 10 - 1) for i in range(21)]
    local_top = max((t for x in samples if (t := _top_at(body, x)) is not None), default=maxy)
    return attach_x, max(local_top, attach_top) + radius + _LOOP_CLEARANCE, attach_top


def _finish_charm(
    body_faces: list[cq.Face], thickness: float, inner: float, wall: float
) -> tuple[cq.Shape, BaseGeometry, tuple[float, float]]:
    """Body plus loop (CH-02) as an exact solid, its 2D profile, and the loop center.

    The loop is a ring with a short connector down into the stroke it joins.
    """
    body2d = to_polygon(body_faces)
    x, y, attach_top = place_loop(body2d, inner, wall)
    outer = inner / 2 + wall
    bottom = attach_top - wall

    profile = unary_union(
        [body2d, Point(x, y).buffer(outer, quad_segs=32), box(x - wall, bottom, x + wall, y)]
    ).difference(Point(x, y).buffer(inner / 2, quad_segs=32))

    ring = cq.Solid.makeCylinder(outer, thickness, cq.Vector(x, y, 0))
    connector = cq.Solid.makeBox(2 * wall, y - bottom, thickness, cq.Vector(x - wall, bottom, 0))
    hole = cq.Solid.makeCylinder(inner / 2, thickness + 2, cq.Vector(x, y, -1))
    solid = _extrude(body_faces, thickness).fuse(ring, connector).clean()
    return solid.cut(hole).clean(), profile, (x, y)


def _loop_dims(inner: float, wall: float, loop: tuple[float, float]) -> list[Dimension]:
    x, y = loop
    outer = inner / 2 + wall
    return [Dimension("front", "h", (x - inner / 2, y), (x + inner / 2, y), inner, y + outer, "Ø")]


# ---------------------------------------------------------------- crescent


def crescent_layout(height: float, width: float) -> tuple[float, float, float]:
    """Outer radius, inner radius and the inner circle's offset to the right."""
    outer = height / 2
    inner = 0.9 * outer
    return outer, inner, width - outer + inner


def star_points(center: tuple[float, float], diameter: float) -> list[tuple[float, float]]:
    """A five-point star with one point to the left (towards the crescent band)."""
    cx, cy = center
    outer, inner = diameter / 2, diameter / 2 * STAR_INNER_RATIO
    points = []
    for i in range(10):
        angle = math.pi + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def build_crescent(p: dict) -> BuiltModel:
    height, width, t = p["height_mm"], p["crescent_width_mm"], p["thickness_mm"]
    outer, inner, offset = crescent_layout(height, width)
    moon = (
        cq.Sketch()
        .push([(0, outer)])
        .circle(outer)
        .push([(offset, outer)])
        .circle(inner, mode="s")
        .reset()
        .vertices()
        .fillet(TIP_RADIUS_MM)  # CH-03: the tips are rounded with 0.3 mm
    )
    faces = list(moon._faces.Faces())
    notes = [f"Tips rounded R{TIP_RADIUS_MM:.1f} (CH-03)"]
    if p["has_star"]:
        star_x = offset - inner + p["star_diameter_mm"] / 2 - STAR_OVERLAP_MM
        star = (
            cq.Sketch()
            .polygon(_closed(star_points((star_x, outer), p["star_diameter_mm"])))
            .reset()
            .vertices()
            .fillet(TIP_RADIUS_MM)
        )
        merged = cq.Compound.makeCompound(faces).fuse(*star._faces.Faces()).clean()
        faces = list(merged.Faces())
        notes.append(f"Five-point star Ø{p['star_diameter_mm']:.1f}, joined to the band")
    solid, profile, loop = _finish_charm(faces, t, p["loop_inner_mm"], p["loop_wall_mm"])
    xmin, _, xmax, _ = profile.bounds
    return BuiltModel(
        solid,
        dimensions=[
            Dimension("front", "v", (xmin, 0), (xmin, height), height, xmin),
            Dimension("front", "h", (-outer, 0), (-outer + width, 0), width, 0.0),
            *_loop_dims(p["loop_inner_mm"], p["loop_wall_mm"], loop),
            Dimension("side", "h", (0, 0), (t, 0), t, 0.0),
        ],
        notes=notes,
        views=("front", "side"),
    )


# ---------------------------------------------------------------- initial


def letter_faces(letter: str, font: str, height: float) -> list[cq.Face]:
    """The letter's outline, `height` tall, centered on x = 0 with its bottom at y = 0."""
    outline = outline_with_height(letter, font, height)
    shift = cq.Vector(-(outline.xmin + outline.xmax) / 2, -outline.ymin, 0)
    return [f.translate(shift) for f in outline.faces]


def build_initial(p: dict) -> BuiltModel:
    height, t = p["height_mm"], p["thickness_mm"]
    faces = letter_faces(p["letter"], p["font"], height)
    solid, profile, loop = _finish_charm(faces, t, p["loop_inner_mm"], p["loop_wall_mm"])
    body = to_polygon(faces)
    xmin, _, xmax, _ = body.bounds
    return BuiltModel(
        solid,
        dimensions=[
            Dimension("front", "v", (xmin, 0), (xmin, height), height, xmin),
            Dimension("front", "h", (xmin, 0), (xmax, 0), xmax - xmin, 0.0),
            *_loop_dims(p["loop_inner_mm"], p["loop_wall_mm"], loop),
            Dimension("side", "h", (0, 0), (t, 0), t, 0.0),
        ],
        notes=[f"Letter {p['letter']}, font {p['font']} (SIL OFL), body height {height:.1f}"],
        views=("front", "side"),
    )


# ---------------------------------------------------------------- disc


def _engraving_layout(text: str) -> tuple[list[tuple[str, float]], float]:
    """Characters and their left edges for 1 mm capitals, and the total width.

    The font's own spacing leaves about 0.1 em between capitals, under the 0.6 mm mold
    limit at engraving sizes, so engraved text is letter-spaced: each character is placed by
    its outline with a fixed gap between neighbours.
    """
    placed, cursor = [], 0.0
    for char in text:
        if char == " ":
            cursor += ENGRAVING_SPACE_RATIO
            continue
        if placed:
            cursor += ENGRAVING_GAP_RATIO
        placed.append((char, cursor))
        cursor += width_per_cap_height(char, ENGRAVING_FONT)
    return placed, cursor


def engraving_width_per_cap(text: str) -> float:
    return _engraving_layout(text)[1]


def engraving_letter_height(text: str, diameter: float) -> float:
    """Capital height of engraved text: the largest that fits 80% of the diameter (CH-06)."""
    fit = ENGRAVING_TEXT_FIT * diameter / engraving_width_per_cap(text)
    return math.floor(min(fit, ENGRAVING_MAX_LETTER_RATIO * diameter) * 10 + 1e-9) / 10


def engraving_text_faces(text: str, diameter: float) -> list[cq.Face]:
    """Engraved text centered on the disc (disc center at (0, diameter / 2))."""
    cap = engraving_letter_height(text, diameter)
    placed, width = _engraving_layout(text)
    faces = []
    for char, left in placed:
        outline = outline_with_cap_height(char, ENGRAVING_FONT, cap)
        shift = cq.Vector((left - width / 2) * cap - outline.xmin, diameter / 2 - cap / 2, 0)
        faces += [f.translate(shift) for f in outline.faces]
    return faces


def _unit_icon(name: str) -> BaseGeometry:
    """Icons drawn in a unit box [-1, 1]²."""
    if name == "moon":
        return Point(0, 0).buffer(1).difference(Point(0.45, 0.2).buffer(0.82))
    if name == "star":
        return Polygon(star_points((0, 0), 2.0)).buffer(0)
    if name == "heart":
        lobes = [Point(-0.48, 0.32).buffer(0.52), Point(0.48, 0.32).buffer(0.52)]
        return unary_union([*lobes, Polygon([(-0.97, 0.2), (0.97, 0.2), (0, -1.0)])])
    if name == "leaf":
        vesica = Point(-0.42, 0).buffer(1).intersection(Point(0.42, 0).buffer(1))
        return affinity.rotate(vesica, 45, origin=(0, 0))
    if name == "bee":
        body = affinity.scale(Point(0, -0.25).buffer(1), 0.42, 0.65)
        wings = [Point(-0.42, 0.42).buffer(0.4), Point(0.42, 0.42).buffer(0.4)]
        return unary_union([body, *wings])
    if name == "wave":
        xs = [-0.9 + 1.8 * i / 60 for i in range(61)]
        line = LineString([(x, 0.35 * math.sin(x * math.pi * 1.5)) for x in xs])
        return line.buffer(0.2, quad_segs=16)
    raise ValueError(f"Unknown icon {name!r}")


def icon_geometry(name: str, diameter: float) -> BaseGeometry:
    """The icon scaled to half the disc diameter and centered on the disc."""
    unit = _unit_icon(name)
    minx, miny, maxx, maxy = unit.bounds
    scale = ICON_SIZE_RATIO * diameter / max(maxx - minx, maxy - miny)
    scaled = affinity.scale(unit, scale, scale, origin=(0, 0))
    cx, cy = scaled.centroid.x, (scaled.bounds[1] + scaled.bounds[3]) / 2
    return affinity.translate(scaled, -cx, diameter / 2 - cy)


def engraving_profile(p: dict) -> BaseGeometry | None:
    """2D outline of the disc's engraving (what the CH-03 check analyses), or None."""
    if p["engraving"] == "text":
        return to_polygon(engraving_text_faces(p["engraving_text"], p["diameter_mm"]))
    if p["engraving"] == "icon":
        return icon_geometry(p["icon"], p["diameter_mm"])
    return None


def build_disc(p: dict) -> BuiltModel:
    d, t, depth = p["diameter_mm"], p["thickness_mm"], p["engraving_depth_mm"]
    disc = cq.Face.makeFromWires(
        cq.Wire.makeCircle(d / 2, cq.Vector(0, d / 2, 0), cq.Vector(0, 0, 1))
    )
    solid, _, loop = _finish_charm([disc], t, p["loop_inner_mm"], p["loop_wall_mm"])
    notes = []
    if p["engraving"] == "text":
        faces = engraving_text_faces(p["engraving_text"], d)
        cap = engraving_letter_height(p["engraving_text"], d)
        notes.append(f"Engraved text, Montserrat ExtraBold, capitals {cap:.1f} high (CH-06)")
    elif p["engraving"] == "icon":
        faces = _faces_of(icon_geometry(p["icon"], d))
        notes.append(f"Engraved icon: {p['icon']} (CH-06)")
    else:
        faces = []
    if faces:
        solid = solid.cut(_extrude(faces, depth + 1.0, z0=t - depth)).clean()
        notes.append(f"Engraving depth {depth:.1f}, front face")
    return BuiltModel(
        solid,
        dimensions=[
            Dimension("front", "h", (-d / 2, d / 2), (d / 2, d / 2), d, 0.0, "Ø"),
            *_loop_dims(p["loop_inner_mm"], p["loop_wall_mm"], loop),
            Dimension("side", "h", (0, 0), (t, 0), t, 0.0),
        ],
        notes=notes,
        views=("front", "side"),
    )


def _closed(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [*points, points[0]]
