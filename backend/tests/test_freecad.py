"""The STEP files open in FreeCAD (Phase 3 "Done when"). Needs freecadcmd: marked `freecad`.

freecadcmd runs as a bounded subprocess (invariant 6): an argument list (no shell), a
timeout, captured output, and the job passed as a JSON file whose path is in an environment
variable (freecadcmd would try to open extra arguments as documents).
"""

import json
import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

from app.core.config import Settings
from app.designs import generate_design
from app.standards.families import get_family

SCRIPT = """
import json, os
import Part
job = json.load(open(os.environ["BEAD_STUDIO_JOB"], encoding="utf-8"))
shape = Part.read(job["step"])
result = {"valid": shape.isValid(), "solids": len(shape.Solids), "volume": shape.Volume}
open(job["out"], "w", encoding="utf-8").write(json.dumps(result))
"""


@pytest.mark.freecad
@pytest.mark.parametrize(("code", "sku"), [("FAC", "GB-1034"), ("CRS", "CH-2034")])
def test_step_opens_in_freecad(
    settings: Settings, freecad: str, tmp_path: Path, code: str, sku: str
) -> None:
    design = generate_design(
        code,
        get_family(code).defaults(),
        sku=sku,
        rev="A",
        settings=settings,
        on_date=date(2026, 11, 17),
    )
    script, job, out = tmp_path / "check_step.py", tmp_path / "job.json", tmp_path / "out.json"
    script.write_text(SCRIPT, encoding="utf-8")
    job.write_text(
        json.dumps({"step": str(design.files["step"]), "out": str(out)}), encoding="utf-8"
    )

    completed = subprocess.run(
        [freecad, str(script)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=os.environ | {"BEAD_STUDIO_JOB": str(job)},
    )

    assert out.exists(), completed.stdout[-2000:] + completed.stderr[-2000:]
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["valid"] and result["solids"] == 1
    assert result["volume"] == pytest.approx(design.measurements["volume_mm3"], rel=1e-4)
