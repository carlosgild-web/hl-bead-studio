"""Render presets: which color or finish a design may be rendered in, and the numbers
Blender gets for it (decision 0003).

The backend decides everything here from the company content (`cad/templates/*.json`):
`blender/render.py` only applies the numbers in the job file. Glass colors (GB-07) apply to
glass beads, plating finishes (CH-05) to charms.
"""

from typing import Any, Literal

from app.core.content import colors, finishes, materials

Kind = Literal["glass_bead", "charm"]

RESOLUTION_PX = 1024  # manual 08-deliverables: 1024 x 1024 PNG
BACKGROUND_HEX = "#f2efea"  # light studio backdrop
SEED = 0  # fixed, so the same design renders the same image

# Surface roughness and clear coat per glass preset (`blender_preset` in colors.json).
_GLASS_SURFACE = {
    "glass_clear": {"roughness": 0.0, "coat": 0.0},
    "glass_translucent": {"roughness": 0.03, "coat": 0.0},
    "glass_opaque": {"roughness": 0.25, "coat": 0.8},  # fire-polished: glossy coat on top
}

# Glass beads keep the mandrel hole upright and are seen a little from above, so the hole
# shows; charms stand up facing the camera (their outline is drawn in the XY plane).
_FRAMING: dict[str, dict[str, Any]] = {
    "glass_bead": {
        "rotation_deg": [0.0, 0.0, 0.0],
        "camera": {"azimuth_deg": 30.0, "elevation_deg": 25.0, "lens_mm": 85.0},
    },
    "charm": {
        "rotation_deg": [90.0, 0.0, 0.0],
        "camera": {"azimuth_deg": 20.0, "elevation_deg": 12.0, "lens_mm": 85.0},
    },
}


class RenderPresetError(ValueError):
    """A color or finish that the design cannot be rendered in."""


def srgb_to_linear(hex_color: str) -> list[float]:
    """`#rrggbb` (sRGB, as in the content files) to linear RGB, which Blender's shader
    inputs expect."""
    if len(hex_color) != 7 or not hex_color.startswith("#"):
        raise ValueError(f"not a #rrggbb color: {hex_color!r}")
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return [round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 5) for c in channels]


def finish_options(kind: Kind) -> list[str]:
    """Colors a glass bead may be rendered in (GB-07), or finishes for a charm (CH-05)."""
    return list(colors() if kind == "glass_bead" else finishes())


def resolve_finish(kind: Kind, params: dict[str, Any], finish: str | None) -> str:
    """The requested color or finish, or the design's own when none is given."""
    if finish is None:
        finish = params["color"] if kind == "glass_bead" else params["finish"]
    if finish not in finish_options(kind):
        rule, what = ("GB-07", "glass color") if kind == "glass_bead" else ("CH-05", "finish")
        raise RenderPresetError(
            f"{finish!r} is not an approved {what} ({rule}): " + ", ".join(finish_options(kind))
        )
    return finish


def material_spec(kind: Kind, finish: str) -> dict[str, Any]:
    """Principled BSDF numbers for one color or finish."""
    if kind == "glass_bead":
        color = colors()[finish]
        surface = _GLASS_SURFACE[color["blender_preset"]]
        return {
            "kind": "glass",
            "base_color": srgb_to_linear(color["hex"]),
            "metallic": 0.0,
            "roughness": surface["roughness"],
            "ior": materials()["borosilicate"]["ior"],
            "transmission": color["transmission"],
            "coat": surface["coat"],
        }
    plating = finishes()[finish]
    return {
        "kind": "metal",
        "base_color": srgb_to_linear(plating["hex"]),
        "metallic": plating["metallic"],
        "roughness": plating["roughness"],
        "ior": 1.5,  # unused by a fully metallic surface
        "transmission": 0.0,
        "coat": 0.0,
    }


def job_spec(
    kind: Kind,
    finish: str,
    *,
    model_path: str,
    output_path: str,
    samples: int,
    resolution: int = RESOLUTION_PX,
) -> dict[str, Any]:
    """The complete job file for `blender/render.py`."""
    framing = _FRAMING[kind]
    return {
        "input": model_path,
        "output": output_path,
        "resolution": resolution,
        "samples": samples,
        "seed": SEED,
        "rotation_deg": list(framing["rotation_deg"]),
        "camera": dict(framing["camera"]),
        "material": material_spec(kind, finish),
        "background": srgb_to_linear(BACKGROUND_HEX),
    }
