"""Stand-in for Blender in the render tests: `python fake_blender.py -- <job.json>`.

It reads the job file like `blender/render.py` and acts as told by `FAKE_BLENDER_MODE`:
`ok` writes a small PNG, `fail` raises (exit 1), `hang` sleeps past any test timeout,
`silent` exits 0 without writing the image. `FAKE_BLENDER_RECORD` names a file to copy the
job into.
"""

import json
import os
import sys
import time
from pathlib import Path

# A valid 1 x 1 PNG.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc0f01f0005fe02fea7d6a4"
    "6b0000000049454e44ae426082"
)


def main() -> None:
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    mode = os.environ.get("FAKE_BLENDER_MODE", "ok")
    print(f"BEADSTUDIO: fake render of {Path(job['input']).name}", flush=True)
    if mode == "fail":
        raise ValueError("material.kind must be glass or metal")
    if mode == "hang":
        time.sleep(60)
    if record := os.environ.get("FAKE_BLENDER_RECORD"):  # let the test see the job file
        Path(record).write_text(json.dumps(job), encoding="utf-8")
    if mode != "silent":
        Path(job["output"]).write_bytes(PNG)


if __name__ == "__main__":
    main()
