"""Build the render gallery of the online demo (decision 0006): `docs/gallery/`.

    backend/.venv/Scripts/python scripts/build_gallery.py      (Windows)
    backend/.venv/bin/python scripts/build_gallery.py          (Linux, macOS)

Every design in `scripts/gallery.json` goes through the real pipeline: `generate_design`
builds and validates it, `queue_render` + `run_job` render each finish with Blender
(BLENDER_BIN). The work happens in `<DATA_DIR>/gallery-build/` (gitignored); only small WebP
images, `manifest.json` and a `README.md` index are written to `docs/gallery/`. Run it again
after changing the studio scene or the materials (`--index-only` rewrites just the index).
"""

import argparse
import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from PIL import Image  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.content import colors, finishes  # noqa: E402
from app.designs import generate_design  # noqa: E402
from app.render import queue_render, recover_interrupted, run_job  # noqa: E402

GALLERY_SPEC = REPO_ROOT / "scripts" / "gallery.json"
GALLERY_DIR = REPO_ROOT / "docs" / "gallery"
WEBP_SIZE_PX = 800
WEBP_QUALITY = 82


def finish_label(finish: str) -> dict[str, str]:
    return (colors().get(finish) or finishes()[finish])["name"]


def write_index(manifest: dict) -> None:
    """`docs/gallery/README.md`: the renders as an image grid, for browsing on GitHub."""
    lines = [
        "# Render gallery",
        "",
        "Catalog renders made locally with the Bead Studio pipeline: CadQuery model, GLB,",
        "Blender Cycles (decisions 0003, 0006 and 0011). The online demo shows these images;",
        "renders run only on a machine with Blender. Rebuild with `scripts/build_gallery.py`.",
        "",
        f"Generated {manifest['generated_at']}; images {manifest['resolution_px']} px WebP.",
        "",
        "| | | |",
        "|---|---|---|",
    ]
    cells = []
    for render in manifest["renders"]:
        name, finish = render["name"], render["finish_name"]["en"]
        cells.append(
            f'<img src="{render["file"]}" width="240" alt="{name}, {finish}">'
            f"<br>**{render['sku']}** {name}<br>{finish} · {render['mass_g']} g"
        )
    for i in range(0, len(cells), 3):
        row = cells[i : i + 3] + [""] * (3 - len(cells[i : i + 3]))
        lines.append("| " + " | ".join(row) + " |")
    (GALLERY_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--samples", type=int, help="Cycles samples (default RENDER_SAMPLES)")
    parser.add_argument("--only", nargs="*", help="render only these SKUs (others are kept)")
    parser.add_argument(
        "--index-only", action="store_true", help="only rewrite README.md from manifest.json"
    )
    args = parser.parse_args(argv)
    manifest_path = GALLERY_DIR / "manifest.json"
    if args.index_only:
        write_index(json.loads(manifest_path.read_text(encoding="utf-8")))
        return 0

    base = get_settings()
    work = base.data_dir / "gallery-build"
    settings = base.model_copy(update={"designs_root": work / "designs", "data_dir": work / "data"})
    shutil.rmtree(work / "designs", ignore_errors=True)  # designs are never overwritten
    recover_interrupted(settings)  # a stopped earlier run leaves jobs `running`
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    previous = (
        json.loads(manifest_path.read_text(encoding="utf-8"))["renders"]
        if manifest_path.exists()
        else []
    )

    designs = json.loads(GALLERY_SPEC.read_text(encoding="utf-8"))["designs"]
    selected = [d for d in designs if not args.only or d["sku"] in args.only]
    renders: list[dict] = [r for r in previous if args.only and r["sku"] not in args.only]
    failures = 0
    started = time.monotonic()
    for design in selected:
        sku, rev = design["sku"], design["rev"]
        generated = generate_design(
            design["family"],
            design["params"],
            sku=sku,
            rev=rev,
            settings=settings,
            name=design["name"],
            actor="gallery",
        )
        for finish in design["finishes"]:
            job = queue_render(settings, sku, rev, finish, actor="gallery", samples=args.samples)
            print(f"{sku} {finish}: rendering (job {job['id']})...", flush=True)
            done = run_job(settings, job["id"])
            if done is None or done["status"] != "done":
                failures += 1
                print(f"  failed: {done and done['error']}", file=sys.stderr)
                continue
            file_name = f"{sku}_{rev}_{finish}.webp"
            with Image.open(settings.designs_root / done["image"]) as image:
                image.convert("RGB").resize(
                    (WEBP_SIZE_PX, WEBP_SIZE_PX), Image.Resampling.LANCZOS
                ).save(GALLERY_DIR / file_name, "WEBP", quality=WEBP_QUALITY, method=6)
            size_kb = (GALLERY_DIR / file_name).stat().st_size / 1024
            print(f"  {file_name}: {done['duration_s']} s, {size_kb:.0f} KB")
            renders.append(
                {
                    "file": file_name,
                    "sku": sku,
                    "rev": rev,
                    # Not a product of the SAP seed: shown as a showcase design (0024).
                    **({"showcase": True} if design.get("showcase") else {}),
                    "name": design["name"],
                    "collection": design["collection"],
                    "family": design["family"],
                    "finish": finish,
                    "finish_name": finish_label(finish),
                    "bbox_mm": generated.measurements["bbox_mm"],
                    "mass_g": generated.measurements["mass_g"],
                    "samples": done["samples"],
                    "render_s": done["duration_s"],
                }
            )

    order = {d["sku"]: i for i, d in enumerate(designs)}
    renders.sort(key=lambda r: (order.get(r["sku"], len(order)), r["file"]))
    manifest = {
        "$comment": "Written by scripts/build_gallery.py. Renders run locally (decision 0006).",
        "generated_at": datetime.now(UTC).date().isoformat(),
        "resolution_px": WEBP_SIZE_PX,
        "renders": renders,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_index(manifest)
    listed = {r["file"] for r in renders}
    for stale in GALLERY_DIR.glob("*.webp"):
        if stale.name not in listed:
            stale.unlink()
    minutes = (time.monotonic() - started) / 60
    print(f"{len(renders)} renders in {GALLERY_DIR} ({minutes:.1f} min, {failures} failed)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
