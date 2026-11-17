"""Confined writes (invariant 4): every design file resolves inside `DESIGNS_ROOT`.

SKU and revision are validated against GEN-04 / GEN-02 allow-lists before they become path
segments, and the resolved path is checked again, so neither `..` nor an absolute path nor a
symlink can move a write outside the root.
"""

from pathlib import Path

from app.standards.identifiers import validate_revision, validate_sku


class UnsafePathError(ValueError):
    """A path that would leave `DESIGNS_ROOT`."""


def confined(root: Path, *parts: str) -> Path:
    """`root / parts`, resolved, guaranteed to stay inside `root`."""
    base = root.resolve()
    target = base.joinpath(*parts).resolve()
    if target != base and not target.is_relative_to(base):
        raise UnsafePathError(f"{'/'.join(parts)!r} leaves the designs folder")
    return target


def design_dir(root: Path, sku: str, rev: str) -> Path:
    """`<DESIGNS_ROOT>/<SKU>/<Rev>/` (manual 08-deliverables)."""
    return confined(root, validate_sku(sku), validate_revision(rev))


def design_file_names(sku: str, rev: str) -> dict[str, str]:
    """The fixed file names of one revision, keyed by kind."""
    stem = f"{validate_sku(sku)}_{validate_revision(rev)}"
    return {
        "step": f"{stem}.step",
        "stl": f"{stem}.stl",
        "glb": f"{stem}.glb",
        "drawing": f"{stem}_drawing.pdf",
        "params": "params.json",
    }
