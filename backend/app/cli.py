"""Command line: `python -m app.cli <command>` (run from `backend/`).

validate      check parameters against the manual and print the result as JSON
generate      write STEP, STL, GLB, drawing PDF and params.json for one revision
measure-fonts measure the approved fonts against CH-03 (the numbers behind CH-07)
render        render a catalog image of a generated revision with Blender
"""

import argparse
import json
import string
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.standards.families import FAMILY_CODES


def _read_params(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cmd_validate(args: argparse.Namespace) -> int:
    from app.standards.validators import validate_parameters

    result = validate_parameters(args.family, _read_params(args.params))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.ok else 2


def _cmd_generate(args: argparse.Namespace) -> int:
    from app.designs import DesignError, InvalidDesignError, generate_design

    try:
        design = generate_design(
            args.family,
            _read_params(args.params),
            sku=args.sku,
            rev=args.rev,
            settings=get_settings(),
            name=args.name,
            sap_material=args.sap_material,
            on_date=date.fromisoformat(args.date) if args.date else None,
        )
    except InvalidDesignError as error:
        print(error, file=sys.stderr)
        for v in error.result.violations:
            hint = ", ".join(f"{s.parameter}={s.value}" for s in v.suggestions)
            print(f"  {v.rule}: {v.message}" + (f" Try {hint}." if hint else ""), file=sys.stderr)
        return 2
    except (DesignError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"{design.sku} rev {design.rev} ({design.family}) -> {design.folder}")
    for kind, path in design.files.items():
        print(f"  {kind:8} {path.name}")
    m = design.measurements
    print(f"  volume {m['volume_mm3']} mm3, mass {m['mass_g']} g, drawing {design.drawing_scale}")
    return 0


def _cmd_measure_fonts(args: argparse.Namespace) -> int:
    from app.geometry.font_metrics import (
        font_minimum,
        measure_engraving_character,
        measure_font,
    )
    from app.standards.rules import FONT_FILES

    for font in FONT_FILES:
        measures = measure_font(font)
        print(f"{font}: CH-07 minimum {font_minimum(measures):.1f} mm")
        for m in sorted(measures, key=lambda m: -(m.min_height_mm or 99))[: args.top]:
            detail = f"{m.pieces} pieces" if m.pieces != 1 else f"{m.min_height_mm} mm"
            print(f"  {m.letter}: {detail}")
    if args.engraving:
        chars = string.ascii_uppercase + string.digits
        results = {c: measure_engraving_character(c) for c in chars}
        print("engraving (capital height):")
        for char, height in sorted(results.items(), key=lambda kv: -(kv[1] or 99))[: args.top]:
            print(f"  {char}: {height} mm")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    from app.render import RenderError, queue_render, run_job

    settings = get_settings()
    try:
        job = queue_render(
            settings, args.sku, args.rev, args.finish, actor="cli", samples=args.samples
        )
    except (RenderError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"job {job['id']}: {job['sku']} rev {job['rev']} in {job['finish']}, rendering...")
    done = run_job(settings, job["id"])
    if done is None:  # the server's worker took it first
        print(f"job {job['id']} is being rendered by the server's worker")
        return 0
    if done["status"] != "done":
        print(f"failed: {done['error']}", file=sys.stderr)
        return 1
    print(f"  {settings.designs_root / done['image']} ({done['duration_s']} s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate parameters against the manual")
    validate.add_argument("--family", required=True, choices=FAMILY_CODES)
    validate.add_argument("--params", required=True, help="JSON file with the parameters")
    validate.set_defaults(func=_cmd_validate)

    generate = commands.add_parser("generate", help="generate the files of a design revision")
    generate.add_argument("--family", required=True, choices=FAMILY_CODES)
    generate.add_argument("--params", required=True, help="JSON file with the parameters")
    generate.add_argument("--sku", required=True, help="GB-1NNN or CH-2NNN (GEN-04)")
    generate.add_argument("--rev", required=True, help="revision letter (GEN-02)")
    generate.add_argument("--name", help="product name for the title block (GEN-03)")
    generate.add_argument("--sap-material", help="SAP material number, without leading zeros")
    generate.add_argument("--date", help="drawing date YYYY-MM-DD (default: today)")
    generate.set_defaults(func=_cmd_generate)

    fonts = commands.add_parser("measure-fonts", help="measure the fonts against CH-03")
    fonts.add_argument("--top", type=int, default=5, help="letters to list per font")
    fonts.add_argument("--engraving", action="store_true", help="also measure engraved text")
    fonts.set_defaults(func=_cmd_measure_fonts)

    render = commands.add_parser("render", help="render a catalog image with Blender")
    render.add_argument("--sku", required=True, help="a generated SKU (GB-1NNN or CH-2NNN)")
    render.add_argument("--rev", required=True, help="revision letter (GEN-02)")
    render.add_argument(
        "--finish", help="glass color (beads) or plating finish (charms); default: the design's"
    )
    render.add_argument("--samples", type=int, help="Cycles samples (default RENDER_SAMPLES)")
    render.set_defaults(func=_cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
