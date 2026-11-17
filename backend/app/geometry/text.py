"""Letters and engraved text from the approved fonts (`cad/fonts/`, SIL Open Font License).

Text is always product data: it is only ever turned into outlines here, never interpreted.
Outlines are built once at a reference size, cached, and scaled on demand.
"""

from dataclasses import dataclass
from functools import lru_cache

import cadquery as cq

from app.core.content import FONTS_DIR
from app.standards.rules import FONT_FILES

_REFERENCE_SIZE = 10.0  # font size (em) of the cached outlines, mm


@dataclass(frozen=True)
class TextOutline:
    """Planar faces of a text in the XY plane, left-aligned at x=0 with the baseline at y=0."""

    faces: tuple[cq.Face, ...]
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin


def font_path(font_id: str) -> str:
    try:
        return str(FONTS_DIR / FONT_FILES[font_id])
    except KeyError:
        raise ValueError(f"Unknown font {font_id!r}") from None


@lru_cache(maxsize=512)
def _reference_outline(text: str, font_id: str) -> TextOutline:
    solid = (
        cq.Workplane("XY")
        .text(
            text,
            _REFERENCE_SIZE,
            1.0,
            fontPath=font_path(font_id),
            halign="left",
            valign="bottom",
            combine=False,
        )
        .val()
    )
    faces = tuple(
        f for f in solid.Faces() if f.geomType() == "PLANE" and f.normalAt().z < -0.5
    )  # the bottom faces at z=0 are the 2D outline
    box = cq.Compound.makeCompound(list(faces)).BoundingBox()
    return TextOutline(faces, box.xmin, box.xmax, box.ymin, box.ymax)


def text_outline(text: str, font_id: str, scale: float = 1.0) -> TextOutline:
    """Outline at `scale` times the reference size (10 mm em)."""
    ref = _reference_outline(text, font_id)
    if scale == 1.0:
        return ref
    faces = tuple(f.scale(scale) for f in ref.faces)
    return TextOutline(
        faces, ref.xmin * scale, ref.xmax * scale, ref.ymin * scale, ref.ymax * scale
    )


def outline_with_height(text: str, font_id: str, height_mm: float) -> TextOutline:
    """Outline scaled so that its bounding box is `height_mm` tall (initial charms)."""
    return text_outline(text, font_id, height_mm / _reference_outline(text, font_id).height)


@lru_cache(maxsize=8)
def cap_height_ratio(font_id: str) -> float:
    """Height of a capital H per mm of font size: the 'letter height' of engraved text."""
    return _reference_outline("H", font_id).height / _REFERENCE_SIZE


def outline_with_cap_height(text: str, font_id: str, cap_height_mm: float) -> TextOutline:
    """Outline scaled so that capitals are `cap_height_mm` tall (engraved text)."""
    return text_outline(
        text, font_id, cap_height_mm / (cap_height_ratio(font_id) * _REFERENCE_SIZE)
    )


def width_per_cap_height(text: str, font_id: str) -> float:
    """Text width divided by its capital height (scale independent)."""
    return _reference_outline(text, font_id).width / (cap_height_ratio(font_id) * _REFERENCE_SIZE)
