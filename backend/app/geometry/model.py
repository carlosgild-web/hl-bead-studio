"""What a family builder returns: the solid plus what the drawing needs to dimension it."""

from dataclasses import dataclass, field
from typing import Literal

import cadquery as cq

ViewName = Literal["front", "top", "side"]


@dataclass(frozen=True)
class Dimension:
    """A linear dimension in a view's 2D coordinates (u to the right, v up), millimetres.

    `start` and `end` are the measured points; `beyond` is the view coordinate of the part's
    outline on the side where the dimension line goes (v for horizontal dimensions, u for
    vertical ones), so the line can be placed just outside the part.
    """

    view: ViewName
    orientation: Literal["h", "v"]
    start: tuple[float, float]
    end: tuple[float, float]
    value: float
    beyond: float
    prefix: str = ""


@dataclass
class BuiltModel:
    shape: cq.Shape
    dimensions: list[Dimension] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    views: tuple[ViewName, ViewName] = ("front", "top")
