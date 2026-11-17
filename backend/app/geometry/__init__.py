"""Parametric product geometry: one CadQuery builder per family (decision 0001)."""

from collections.abc import Callable

from app.geometry.beads import build_faceted, build_lentil, build_rondelle, build_round
from app.geometry.charms import build_crescent, build_disc, build_initial
from app.geometry.model import BuiltModel, Dimension

BUILDERS: dict[str, Callable[[dict], BuiltModel]] = {
    "RND": build_round,
    "FAC": build_faceted,
    "LEN": build_lentil,
    "RON": build_rondelle,
    "CRS": build_crescent,
    "INI": build_initial,
    "DSC": build_disc,
}


def build_model(family: str, params: dict) -> BuiltModel:
    """Build the solid for parameters that `standards.validators` has already accepted."""
    return BUILDERS[family](params)


__all__ = ["BUILDERS", "BuiltModel", "Dimension", "build_model"]
