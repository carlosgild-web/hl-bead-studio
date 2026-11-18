"""Run `blender/render.py` as a bounded subprocess (invariant 6).

The command is an argument list (no shell), every input goes through a JSON job file, the
output of Blender is captured to a log file next to the render, and the process is killed
after `RENDER_TIMEOUT_S`.
"""

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, Settings

BLENDER_SCRIPT = REPO_ROOT / "blender" / "render.py"
LOG_PREFIX = "BEADSTUDIO:"
BLENDER_MISSING = (
    "Blender is not installed on this server (BLENDER_BIN), so catalog renders are not "
    "available here: they run on a designer's computer. The render gallery shows "
    "pre-generated renders."
)


class RenderFailed(Exception):
    """Blender did not produce the image; the message says why in one line."""


def blender_available(settings: Settings) -> bool:
    """BLENDER_BIN is an existing file or a program on PATH. Checked before a render card
    opens and again on the click, so a server without Blender says so at once instead of
    queuing a job that can only fail."""
    configured = settings.blender_bin
    return Path(configured).is_file() or shutil.which(configured) is not None


def blender_command(settings: Settings) -> list[str]:
    """Blender in the background with factory settings and no auto-run scripts; a Python
    error in the script becomes exit status 1. The job file path is appended last."""
    return [
        settings.blender_bin,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--python-exit-code",
        "1",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
    ]


def _failure_reason(log_path: Path) -> str:
    """The most useful line of a failed run: the Python error, else the last line."""
    try:
        lines = [line.strip() for line in log_path.read_text(errors="replace").splitlines()]
    except OSError:
        return "no log"
    lines = [line for line in lines if line]
    for line in reversed(lines):
        if line.split(":")[0].endswith(("Error", "Exception")) or line.startswith("SystemExit"):
            return line[:300]
    return lines[-1][:300] if lines else "no output"


def run_blender(
    job: dict[str, Any],
    *,
    job_path: Path,
    log_path: Path,
    timeout_s: float,
    command: list[str],
) -> float:
    """Write the job file, run Blender, check the image exists. Returns seconds taken."""
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        try:
            completed = subprocess.run(
                [*command, str(job_path)],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                check=False,
            )
        except FileNotFoundError as error:
            raise RenderFailed(
                f"Blender not found ({command[0]!r}); set BLENDER_BIN to blender's path"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise RenderFailed(f"Blender ran longer than {timeout_s:.0f} s and was stopped") from (
                error
            )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise RenderFailed(
            f"Blender exited with status {completed.returncode}: {_failure_reason(log_path)}"
        )
    if not Path(job["output"]).is_file():
        raise RenderFailed("Blender finished but wrote no image")
    return elapsed
