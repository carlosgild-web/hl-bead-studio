"""The backend for the Playwright end-to-end test: `python scripts/e2e_server.py [--port 8010]`.

Everything is the real app (API, tools, validators, CadQuery, drawing, confirmation gate,
render queue, audit) except three stand-ins, so the test needs no SAP service, no model and
no Blender:

- SAP: the in-memory OData stand-in from `backend/app/sap/memory.py`;
- the model: a FakeClient whose script is picked by keywords in the designer's message
  ("reserve", "generate", "render"); any other message gets demo mode's real answer from
  the Q&A bank (DemoClient, decision 0022);
- Blender: `backend/tests/fake_blender.py`, which writes a small PNG.

Data and designs go to a fresh temporary folder, removed on exit.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from functools import partial
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"

FAC_10 = {
    "diameter_mm": 10.0,
    "hole_mm": 1.5,
    "facet_count": 16,
    "facet_rows": 2,
    "color": "amber",
}
NAME = "Amber Glow Faceted"


def scripted_client(sap):
    """A FakeClient for the designer's latest message: plays the model of the design flow,
    or leaves the message to demo mode (no script)."""
    from app.llm.demo import designer_text
    from app.llm.fake import FakeClient, call, say

    def latest_reserved() -> str:
        ours = [sku for sku, m in sap.materials.items() if m.get("CreatedBy") == "BEADSTUDIO"]
        return max(ours) if ours else "GB-0000"

    class DemoClient(FakeClient):
        def chat(self, messages, tools, *, allow_tools=True):
            if self._script is None:
                text = designer_text(messages).lower()
                if "generate" in text:
                    sku = latest_reserved()
                    script = [
                        call("request_generate_design", sku=sku, rev="A", params=FAC_10),
                        say(f"Confirm the card to generate {sku} revision A."),
                    ]
                elif "render" in text:
                    sku = latest_reserved()
                    script = [
                        call("request_render", sku=sku, rev="A"),
                        say(f"Confirm the card to queue a render of {sku}."),
                    ]
                elif "reserve" in text:
                    script = [
                        call("propose_parameters", family="FAC", params=FAC_10),
                        call("preview_geometry", family="FAC", params=FAC_10),
                        call("check_catalog", name=NAME, family="FAC"),
                        call(
                            "request_reserve_sku",
                            family="FAC",
                            name=NAME,
                            collection="Amber Hollow",
                        ),
                        say(
                            "I proposed a 10 mm faceted bead in amber and checked it against "
                            f"the manual. Confirm the card to reserve a SKU for {NAME}."
                        ),
                    ]
                else:
                    script = None  # demo mode: DemoClient answers from the Q&A bank
                self._script = script
            return super().chat(messages, tools, allow_tools=allow_tools)

    return DemoClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="bead-e2e-"))
    os.environ.update(
        {
            "LLM_PROVIDER": "fake",
            "DATA_DIR": str(work / "data"),
            "DESIGNS_ROOT": str(work / "designs"),
            # A file that exists, so the render card's Blender check passes; the worker runs
            # fake_blender.py instead (below).
            "BLENDER_BIN": sys.executable,
            "RATE_LIMIT_PER_MINUTE": "0",
            "DAILY_TOKEN_CAP": "0",
            "DESIGNS_RETENTION_HOURS": "0",
        }
    )
    sys.path.insert(0, str(BACKEND))

    import uvicorn

    import app.main as main_module
    from app.api import deps
    from app.render import RenderWorker
    from app.sap.memory import InMemorySap

    sap = InMemorySap()
    client_class = scripted_client(sap)
    fake_blender = [sys.executable, str(BACKEND / "tests" / "fake_blender.py"), "--"]
    main_module.RenderWorker = partial(RenderWorker, poll_s=0.5, command=fake_blender)
    main_module.app.dependency_overrides[deps.get_sap_factory] = lambda: sap.client
    main_module.app.dependency_overrides[deps.get_llm_factory] = lambda: client_class

    try:
        uvicorn.run(main_module.app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
