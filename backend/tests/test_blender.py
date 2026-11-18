"""Real Blender renders, small and fast (marked `blender`, skipped without BLENDER_BIN)."""

import pytest
from PIL import Image

from app.core.config import Settings
from app.render import queue_render, run_job

pytestmark = pytest.mark.blender


@pytest.mark.parametrize(("sku", "finish"), [("GB-1034", "clear"), ("CH-2034", "rhodium")])
def test_blender_renders_a_bead_and_a_charm(
    designed: Settings, blender: str, sku: str, finish: str
) -> None:
    settings = designed.model_copy(update={"blender_bin": blender, "render_timeout_s": 300})
    job = queue_render(settings, sku, "A", finish, actor="tester", samples=4, resolution=128)

    done = run_job(settings, job["id"])

    assert done["status"] == "done", done["error"]
    with Image.open(settings.designs_root / done["image"]) as image:
        assert image.size == (128, 128)
        assert image.mode == "RGB"
        # Not a blank frame: the product stands out from the backdrop.
        low, high = image.convert("L").getextrema()
        assert high - low > 40
