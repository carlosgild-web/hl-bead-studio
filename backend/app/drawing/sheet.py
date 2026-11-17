"""The technical drawing: two first-angle views with dimensions on the H&L A4 sheet.

Decision 0009: the views come from OpenCascade's hidden-line removal (the same kernel FreeCAD
TechDraw uses), the sheet is `cad/templates/hl_title_block_A4.svg`, and the PDF is rendered
in Python (svglib + reportlab). Every text field is XML-escaped: names and engraved text are
data, never markup (invariant 8).
"""

import io
import re
from dataclasses import dataclass
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

from app.core.content import TEMPLATES_DIR
from app.drawing.projection import Projection, project
from app.geometry.model import BuiltModel, Dimension
from app.standards.rules import GENERAL_TOLERANCE_MM, RULE_EDITION

SCALES = (10, 5, 2, 1)
_DIM_OFFSET = 7.0  # paper mm between the part and a dimension line
_DIM_STEP = 6.0  # paper mm between stacked dimension lines on the same side
_DIM_MARGIN = 16.0  # paper mm kept around each view for its dimensions
_ARROW = 2.2
_TEXT = 3.0
_LINE_VISIBLE = 0.5
_LINE_HIDDEN = 0.25
_LINE_THIN = 0.18

# Regions of the sheet (paper mm): x0, y0, x1, y1.
_BEAD_VIEWS = (12.0, 12.0, 145.0, 198.0)  # front above top (first angle)
_BEAD_NOTES = (152.0, 22.0)
_CHARM_VIEWS = (12.0, 12.0, 285.0, 146.0)  # front, side to its right (first angle)
_CHARM_NOTES = (14.0, 156.0)


@dataclass(frozen=True)
class TitleBlock:
    name: str
    sku: str
    rev: str
    sap_material: str
    family: str
    material: str
    mass: str
    date: str
    designer: str
    file: str


def _fmt(value: float) -> str:
    return f"{value:.1f}"


def _choose_scale(sizes: list[tuple[float, float]], area_w: float, area_h: float, stacked: bool):
    for scale in SCALES:
        widths = [w * scale + 2 * _DIM_MARGIN for w, _ in sizes]
        heights = [h * scale + 2 * _DIM_MARGIN for _, h in sizes]
        if stacked and max(widths) <= area_w and sum(heights) <= area_h:
            return scale
        if not stacked and sum(widths) <= area_w and max(heights) <= area_h:
            return scale
    return SCALES[-1]


class _View:
    def __init__(self, name: str, projection: Projection, scale: float, cx: float, cy: float):
        self.name, self.projection, self.scale = name, projection, scale
        umin, vmin, umax, vmax = projection.bounds
        self.bounds = (umin, vmin, umax, vmax)
        # place the view's bounding box center at (cx, cy) on the paper
        self.ox = cx - (umin + umax) / 2 * scale
        self.oy = cy + (vmin + vmax) / 2 * scale

    def xy(self, u: float, v: float) -> tuple[float, float]:
        return self.ox + u * self.scale, self.oy - v * self.scale


def _path(view: _View, line: list[tuple[float, float]]) -> str:
    points = [view.xy(u, v) for u, v in line]
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in points)


def _arrow(x: float, y: float, dx: float, dy: float) -> str:
    """Filled arrowhead with its tip at (x, y), pointing along (dx, dy)."""
    px, py = -dy, dx
    bx, by = x - dx * _ARROW, y - dy * _ARROW
    w = _ARROW * 0.18
    return (
        f'<path d="M{x:.3f},{y:.3f} L{bx + px * w:.3f},{by + py * w:.3f} '
        f'L{bx - px * w:.3f},{by - py * w:.3f} Z" fill="#000000" stroke="none"/>'
    )


def _dimension(view: _View, dim: Dimension, level: int) -> str:
    umin, vmin, umax, vmax = view.bounds
    (u1, v1), (u2, v2) = dim.start, dim.end
    text = escape(f"{dim.prefix}{_fmt(dim.value)}")
    out = []
    style = f'stroke="#000000" stroke-width="{_LINE_THIN}" fill="none"'
    offset = (_DIM_OFFSET + level * _DIM_STEP) / view.scale
    if dim.orientation == "h":
        below = dim.beyond <= (vmin + vmax) / 2
        line_v = dim.beyond - offset if below else dim.beyond + offset
        x1, y1 = view.xy(u1, v1)
        x2, y2 = view.xy(u2, v2)
        _, ly = view.xy(0, line_v)
        gap = 1.0 if below else -1.0
        out.append(f'<path d="M{x1:.3f},{y1 + gap:.3f} L{x1:.3f},{ly + gap:.3f}" {style}/>')
        out.append(f'<path d="M{x2:.3f},{y2 + gap:.3f} L{x2:.3f},{ly + gap:.3f}" {style}/>')
        if x2 - x1 >= 2 * _ARROW + 1:
            out.append(f'<path d="M{x1:.3f},{ly:.3f} L{x2:.3f},{ly:.3f}" {style}/>')
            out.append(_arrow(x1, ly, -1, 0) + _arrow(x2, ly, 1, 0))
        else:  # small feature: arrows from outside
            out.append(f'<path d="M{x1 - 5:.3f},{ly:.3f} L{x2 + 5:.3f},{ly:.3f}" {style}/>')
            out.append(_arrow(x1, ly, 1, 0) + _arrow(x2, ly, -1, 0))
        out.append(
            f'<text x="{(x1 + x2) / 2:.3f}" y="{ly - 1:.3f}" font-size="{_TEXT}" '
            f'text-anchor="middle" font-family="Helvetica">{text}</text>'
        )
    else:
        left = dim.beyond <= (umin + umax) / 2
        line_u = dim.beyond - offset if left else dim.beyond + offset
        x1, y1 = view.xy(u1, v1)
        x2, y2 = view.xy(u2, v2)
        lx, _ = view.xy(line_u, 0)
        gap = -1.0 if left else 1.0
        out.append(f'<path d="M{x1 + gap:.3f},{y1:.3f} L{lx + gap:.3f},{y1:.3f}" {style}/>')
        out.append(f'<path d="M{x2 + gap:.3f},{y2:.3f} L{lx + gap:.3f},{y2:.3f}" {style}/>')
        out.append(f'<path d="M{lx:.3f},{y1:.3f} L{lx:.3f},{y2:.3f}" {style}/>')
        top, bottom = min(y1, y2), max(y1, y2)
        out.append(_arrow(lx, bottom, 0, 1) + _arrow(lx, top, 0, -1))
        cy = (y1 + y2) / 2
        out.append(
            f'<text x="{lx - 1:.3f}" y="{cy:.3f}" font-size="{_TEXT}" text-anchor="middle" '
            f'font-family="Helvetica" transform="rotate(-90 {lx - 1:.3f} {cy:.3f})">{text}</text>'
        )
    return "\n".join(out)


def _view_svg(view: _View, dims: list[Dimension]) -> str:
    parts = [f'<g id="view-{view.name}">']
    for line in view.projection.hidden:
        parts.append(
            f'<path d="{_path(view, line)}" fill="none" stroke="#000000" '
            f'stroke-width="{_LINE_HIDDEN}" stroke-dasharray="1.2,0.8"/>'
        )
    for line in view.projection.visible:
        parts.append(
            f'<path d="{_path(view, line)}" fill="none" stroke="#000000" '
            f'stroke-width="{_LINE_VISIBLE}" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    levels: dict[tuple[str, bool], int] = {}
    for dim in dims:
        umin, vmin, umax, vmax = view.bounds
        side = (
            dim.beyond <= (vmin + vmax) / 2
            if dim.orientation == "h"
            else dim.beyond <= (umin + umax) / 2
        )
        key = (dim.orientation, side)
        parts.append(_dimension(view, dim, levels.get(key, 0)))
        levels[key] = levels.get(key, 0) + 1
    x, y = view.xy(view.bounds[0], view.bounds[1])
    label = {"front": "FRONT", "top": "TOP", "side": "LEFT SIDE"}[view.name]
    parts.append(
        f'<text x="{(view.xy(view.bounds[0], 0)[0] + view.xy(view.bounds[2], 0)[0]) / 2:.3f}" '
        f'y="{y + _DIM_MARGIN + 2:.3f}" font-size="2.6" text-anchor="middle" fill="#555555" '
        f'font-family="Helvetica">{label}</text>'
    )
    parts.append("</g>")
    return "\n".join(parts)


def _logo(x: float, y: float, height: float) -> str:
    text = (TEMPLATES_DIR / "hl_logo.svg").read_text(encoding="utf-8")
    inner = re.search(r"<svg[^>]*>(.*)</svg>", text, re.S).group(1)
    # svglib ignores `opacity`; use the fill and stroke opacities it understands.
    inner = re.sub(r'\bopacity="([^"]+)"', r'fill-opacity="\1" stroke-opacity="\1"', inner)
    k = height / 84
    return f'<g transform="translate({x:.3f},{y:.3f}) scale({k:.5f}) translate(-8,-8)">{inner}</g>'


def drawing_svg(model: BuiltModel, kind: str, title: TitleBlock) -> str:
    projections = {name: project(model.shape, kind, name) for name in model.views}
    sizes = [(b[2] - b[0], b[3] - b[1]) for b in (projections[n].bounds for n in model.views)]
    stacked = kind == "glass_bead"
    x0, y0, x1, y1 = _BEAD_VIEWS if stacked else _CHARM_VIEWS
    scale = _choose_scale(sizes, x1 - x0, y1 - y0, stacked)

    views = []
    if stacked:
        heights = [h * scale + 2 * _DIM_MARGIN for _, h in sizes]
        top = y0 + ((y1 - y0) - sum(heights)) / 2
        for name, height in zip(model.views, heights, strict=True):
            views.append(_View(name, projections[name], scale, (x0 + x1) / 2, top + height / 2))
            top += height
    else:
        widths = [w * scale + 2 * _DIM_MARGIN for w, _ in sizes]
        left = x0 + ((x1 - x0) - sum(widths)) / 2
        for name, width in zip(model.views, widths, strict=True):
            views.append(_View(name, projections[name], scale, left + width / 2, (y0 + y1) / 2))
            left += width

    body = [_view_svg(v, [d for d in model.dimensions if d.view == v.name]) for v in views]
    nx, ny = _BEAD_NOTES if stacked else _CHARM_NOTES
    notes = [*model.notes, f"General tolerance ±{GENERAL_TOLERANCE_MM:.1f} mm (GEN-01)"]
    body.append(f'<text x="{nx}" y="{ny}" font-size="3" font-family="Helvetica-Bold">NOTES</text>')
    for i, note in enumerate(notes, start=1):
        body.append(
            f'<text x="{nx}" y="{ny + 5 * i}" font-size="2.6" font-family="Helvetica">'
            f"{i}. {escape(note)}</text>"
        )

    fields = {
        "name": title.name,
        "sku": title.sku,
        "rev": title.rev,
        "sap_material": title.sap_material,
        "family": title.family,
        "material": title.material,
        "mass": title.mass,
        "scale": f"{scale}:1",
        "date": title.date,
        "designer": title.designer,
        "file": title.file,
        "tolerance": f"±{GENERAL_TOLERANCE_MM:.1f}",
        "rule_edition": RULE_EDITION,
    }
    sheet = (TEMPLATES_DIR / "hl_title_block_A4.svg").read_text(encoding="utf-8")
    sheet = re.sub(r"\{\{(\w+)\}\}", lambda m: escape(fields[m.group(1)]), sheet)
    sheet = sheet.replace("<!-- LOGO -->", _logo(149.5, 149.5, 13.5))
    return sheet.replace("<!-- VIEWS -->", "\n".join(body))


def drawing_scale(svg: str) -> str:
    """The scale written in the title block (for reports and tests)."""
    match = re.search(r">(\d+:1)<", svg)
    return match.group(1) if match else ""


def svg_to_pdf(svg: str) -> bytes:
    drawing = svg2rlg(io.BytesIO(svg.encode("utf-8")))
    if drawing is None:
        raise RuntimeError("The drawing SVG could not be rendered to PDF")
    out = io.BytesIO()
    renderPDF.drawToFile(drawing, out, title="Hilda & Luna Beadworks technical drawing")
    return out.getvalue()
