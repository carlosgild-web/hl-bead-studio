"""Glass bead builders (RND, FAC, LEN, RON). Millimetres; the hole runs along Z.

Each builder takes parameters already checked by `standards.validators` and returns an exact
CadQuery solid centered at the origin.
"""

import math

import cadquery as cq

from app.geometry.model import BuiltModel, Dimension

_HOLE_CLEARANCE = 0.5  # minimum glass ring left around the hole on a faceted bead's end flat


def _hole(diameter: float, length: float) -> cq.Solid:
    return cq.Solid.makeCylinder(
        diameter / 2, length, cq.Vector(0, 0, -length / 2), cq.Vector(0, 0, 1)
    )


def build_round(p: dict) -> BuiltModel:
    d, h = p["diameter_mm"], p["hole_mm"]
    shape = cq.Solid.makeSphere(d / 2, angleDegrees1=-90, angleDegrees2=90).cut(_hole(h, 2 * d))
    return BuiltModel(
        shape,
        dimensions=[
            Dimension("front", "h", (-d / 2, 0), (d / 2, 0), d, beyond=-d / 2, prefix="Ø"),
            Dimension("top", "h", (-h / 2, 0), (h / 2, 0), h, beyond=-d / 2, prefix="Ø"),
        ],
        notes=[f"Through hole Ø{h:.1f} (mandrel, GB-01)"],
    )


def faceted_layout(d: float, facets: int, rows: int, hole: float) -> tuple[list, float]:
    """Facet planes as (tilt rad, azimuth rad, distance from center) and the end-flat height.

    The equatorial cross-section is a regular polygon whose corners lie on the bead diameter,
    so the flat-to-hole wall is the GB-02 formula (d/2)·cos(180°/n) − h/2. One row is a
    faceted barrel, two rows a bicone, three rows a barrel with bevelled ends.
    """
    r = d / 2
    p_eq = r * math.cos(math.pi / facets)
    step = 2 * math.pi / facets
    corner = math.pi / facets  # rotate so that a corner lies on +X (the front view shows d)

    if rows == 1:
        tilts, end_ratio = [(0.0, 0.0, p_eq)], 0.70
    elif rows == 2:
        tilt = math.radians(30)
        tilts = [(tilt, 0.0, p_eq * math.cos(tilt)), (-tilt, 0.0, p_eq * math.cos(tilt))]
        end_ratio = 0.80
    else:
        tilt = math.radians(45)
        tilts = [(0.0, 0.0, p_eq), (tilt, corner, p_eq), (-tilt, corner, p_eq)]
        end_ratio = 0.85

    planes = [
        (phi, corner + offset + k * step, dist)
        for phi, offset, dist in tilts
        for k in range(facets)
    ]
    z_end = end_ratio * r
    for phi, _, dist in planes:
        if phi:  # keep a glass ring around the hole on the end flats
            limit = (dist - (hole / 2 + _HOLE_CLEARANCE) * math.cos(phi)) / math.sin(abs(phi))
            z_end = min(z_end, limit)
    return planes, z_end


def _convex_polyhedron(planes: list[tuple[cq.Vector, float]], size: float) -> cq.Solid:
    """The solid {x : n·x <= d for every (n, d)}, built face by face.

    Each face is a large square on its plane clipped by every other half-space (convex
    polygon clipping), so the solid has exact planar faces and needs no boolean operations,
    which are slow with dozens of tilted cutting tools.
    """
    faces = []
    for i, (normal, dist) in enumerate(planes):
        helper = cq.Vector(0, 0, 1) if abs(normal.z) < 0.9 else cq.Vector(1, 0, 0)
        u = helper.cross(normal).normalized()
        v = normal.cross(u)
        center = normal * dist
        polygon = [center + (u * a + v * b) * size for a, b in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
        for j, (other, other_dist) in enumerate(planes):
            if i == j or not polygon:
                continue
            clipped = []
            for k, point in enumerate(polygon):
                nxt = polygon[(k + 1) % len(polygon)]
                s1, s2 = other.dot(point) - other_dist, other.dot(nxt) - other_dist
                if s1 <= 0:
                    clipped.append(point)
                if (s1 < 0 < s2) or (s2 < 0 < s1):
                    clipped.append(point + (nxt - point) * (s1 / (s1 - s2)))
            polygon = clipped
        unique = []
        for point in polygon:
            if not unique or (point - unique[-1]).Length > 1e-7:
                unique.append(point)
        if len(unique) > 2 and (unique[0] - unique[-1]).Length <= 1e-7:
            unique.pop()
        if len(unique) >= 3:
            faces.append(cq.Face.makeFromWires(cq.Wire.makePolygon(unique, close=True)))
    return cq.Solid.makeSolid(cq.Shell.makeShell(faces)).fix()


def build_faceted(p: dict) -> BuiltModel:
    d, n, rows, h = p["diameter_mm"], p["facet_count"], p["facet_rows"], p["hole_mm"]
    r = d / 2
    layout, z_end = faceted_layout(d, n, rows, h)

    planes = [
        (
            cq.Vector(
                math.cos(phi) * math.cos(theta), math.cos(phi) * math.sin(theta), math.sin(phi)
            ),
            dist,
        )
        for phi, theta, dist in layout
    ]
    planes += [(cq.Vector(0, 0, 1), z_end), (cq.Vector(0, 0, -1), z_end)]
    shape = _convex_polyhedron(planes, size=4 * r).cut(_hole(h, 4 * z_end))
    return BuiltModel(
        shape,
        dimensions=[
            Dimension("front", "h", (-r, 0), (r, 0), d, beyond=-z_end, prefix="Ø"),
            Dimension("front", "v", (0, -z_end), (0, z_end), 2 * z_end, beyond=-r),
            Dimension("top", "h", (-h / 2, 0), (h / 2, 0), h, beyond=-r, prefix="Ø"),
        ],
        notes=[
            f"{n} facets per row, {rows} row(s); Ø{d:.1f} across the facet corners (GB-05)",
            f"Through hole Ø{h:.1f} (mandrel, GB-01)",
        ],
    )


def lentil_profile(d: float, t: float) -> tuple[float, float, float]:
    """Cap radius, rim radius and cap-to-rim tangent point x of a lentil's section."""
    rim = 0.25 * t
    a, b = d / 2 - rim, t / 2
    cap = (a * a + b * b - rim * rim) / (2 * (b - rim))
    return cap, rim, a


def build_lentil(p: dict) -> BuiltModel:
    """A lens with a rounded rim; the lens axis is Y and the hole crosses it along Z."""
    d, t, h = p["diameter_mm"], p["thickness_mm"], p["hole_mm"]
    cap, rim, a = lentil_profile(d, t)
    b = t / 2
    # Section in the XY plane (x radial, y along the lens axis), revolved about Y.
    center = cq.Vector(0, b - cap)
    rim_center = cq.Vector(a, 0)
    tangent = center + (rim_center - center) * (cap / (rim_center - center).Length)
    start_angle = math.atan2(b - center.y, 0 - center.x)
    end_angle = math.atan2(tangent.y - center.y, tangent.x - center.x)
    mid_angle = (start_angle + end_angle) / 2
    cap_mid = (center.x + cap * math.cos(mid_angle), center.y + cap * math.sin(mid_angle))
    section = (
        cq.Workplane("XY")
        .moveTo(0, b)
        .threePointArc(cap_mid, (tangent.x, tangent.y))
        .threePointArc((d / 2, 0), (tangent.x, -tangent.y))
        .threePointArc((cap_mid[0], -cap_mid[1]), (0, -b))
        .close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
        .val()
    )
    shape = section.cut(_hole(h, 2 * d))
    return BuiltModel(
        shape,
        dimensions=[
            Dimension("front", "h", (-d / 2, 0), (d / 2, 0), d, beyond=-d / 2, prefix="Ø"),
            Dimension("top", "v", (0, -b), (0, b), t, beyond=-d / 2),
            Dimension("top", "h", (-h / 2, 0), (h / 2, 0), h, beyond=-b, prefix="Ø"),
        ],
        notes=[f"Through hole Ø{h:.1f} across the diameter (mandrel, GB-01)"],
    )


def build_rondelle(p: dict) -> BuiltModel:
    d, height, h = p["diameter_mm"], p["height_mm"], p["hole_mm"]
    r = d / 2
    radius = min(0.45 * height, r - h / 2 - 0.3)  # rounded rim, flat ends around the hole
    body = (
        cq.Workplane("XY")
        .circle(r)
        .extrude(height)
        .translate((0, 0, -height / 2))
        .edges("%CIRCLE")
        .fillet(radius)
        .val()
    )
    shape = body.cut(_hole(h, 2 * height))
    return BuiltModel(
        shape,
        dimensions=[
            Dimension("front", "h", (-r, 0), (r, 0), d, beyond=-height / 2, prefix="Ø"),
            Dimension("front", "v", (0, -height / 2), (0, height / 2), height, beyond=-r),
            Dimension("top", "h", (-h / 2, 0), (h / 2, 0), h, beyond=-r, prefix="Ø"),
        ],
        notes=[f"Through hole Ø{h:.1f} (mandrel, GB-01)"],
    )
