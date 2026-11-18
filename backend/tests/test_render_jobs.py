"""Render jobs: queue, atomic claim, the bounded Blender run, failures, audit and recovery.

Blender is replaced by tests/fake_blender.py; test_blender.py runs the real one.
"""

import json
import time
from pathlib import Path

import pytest

from app.cli import main
from app.core.config import Settings
from app.core.paths import UnsafePathError
from app.db import read_audit
from app.render import (
    RenderError,
    RenderWorker,
    get_job,
    list_jobs,
    queue_render,
    recover_interrupted,
    run_job,
)
from app.render import jobs as jobs_module
from app.render.runner import BLENDER_SCRIPT, blender_command
from app.standards.identifiers import InvalidIdentifierError


def _actions(settings: Settings, sku: str) -> list[str]:
    return [row["action"] for row in read_audit(settings.data_dir, sku=sku)]


def test_queues_in_the_designs_own_finish(designed: Settings) -> None:
    job = queue_render(designed, "CH-2034", "A", actor="tester")

    assert job["status"] == "queued"
    assert job["finish"] == "gold_plate"
    assert job["samples"] == designed.render_samples
    assert job["resolution"] == 1024
    queued = read_audit(designed.data_dir, sku="CH-2034")[-1]
    assert queued["action"] == "render.queued"
    assert queued["actor"] == "tester"
    assert queued["details"] == {"job_id": job["id"], "finish": "gold_plate", "samples": 64}


def test_refuses_a_finish_of_the_wrong_kind(designed: Settings) -> None:
    with pytest.raises(RenderError, match="GB-07"):
        queue_render(designed, "GB-1034", "A", "rhodium", actor="tester")
    assert list_jobs(designed) == []


def test_refuses_a_revision_that_was_not_generated(designed: Settings) -> None:
    with pytest.raises(RenderError, match="generate it first"):
        queue_render(designed, "GB-1034", "B", actor="tester")


@pytest.mark.parametrize(("sku", "rev"), [("../GB-1034", "A"), ("GB-1034", "../A"), ("x", "I")])
def test_invalid_identifiers_never_reach_the_file_system(
    designed: Settings, sku: str, rev: str
) -> None:
    with pytest.raises((InvalidIdentifierError, UnsafePathError)):
        queue_render(designed, sku, rev, actor="tester")


def test_runs_a_job_and_moves_the_image_into_place(
    designed: Settings, fake_blender: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_BLENDER_RECORD", str(tmp_path / "job.json"))
    job = queue_render(designed, "GB-1034", "A", "amber", actor="tester", samples=16)

    done = run_job(designed, job["id"], command=fake_blender)

    assert done is not None
    assert done["status"] == "done"
    assert done["image"] == "GB-1034/A/render/GB-1034_A_amber.png"
    assert done["duration_s"] is not None
    render_folder = designed.designs_root / "GB-1034" / "A" / "render"
    assert sorted(p.name for p in render_folder.iterdir()) == [
        "GB-1034_A_amber.log",
        "GB-1034_A_amber.png",
    ]  # the work folder is gone
    assert (
        "BEADSTUDIO: fake render of GB-1034_A.glb"
        in (render_folder / "GB-1034_A_amber.log").read_text()
    )
    sent = json.loads((tmp_path / "job.json").read_text(encoding="utf-8"))
    assert sent["samples"] == 16
    assert sent["material"]["kind"] == "glass"
    assert Path(sent["input"]).name == "GB-1034_A.glb"
    assert _actions(designed, "GB-1034")[-2:] == ["render.queued", "render.done"]


def test_a_job_runs_once(designed: Settings, fake_blender: list[str]) -> None:
    job = queue_render(designed, "CH-2034", "A", actor="tester")

    assert run_job(designed, job["id"], command=fake_blender) is not None
    assert run_job(designed, job["id"], command=fake_blender) is None
    assert run_job(designed, 9999, command=fake_blender) is None


def test_rendering_again_replaces_the_image(designed: Settings, fake_blender: list[str]) -> None:
    for _ in range(2):
        job = queue_render(designed, "CH-2034", "A", "rhodium", actor="tester")
        assert run_job(designed, job["id"], command=fake_blender)["status"] == "done"

    assert [j["status"] for j in list_jobs(designed, sku="CH-2034")] == ["done", "done"]


@pytest.mark.parametrize(
    ("mode", "timeout", "message"),
    [
        ("fail", 30, "exited with status 1: ValueError: material.kind must be glass or metal"),
        ("silent", 30, "wrote no image"),
        ("hang", 1, "longer than 1 s and was stopped"),
    ],
)
def test_a_failed_run_fails_the_job(
    designed: Settings,
    fake_blender: list[str],
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    timeout: int,
    message: str,
) -> None:
    monkeypatch.setenv("FAKE_BLENDER_MODE", mode)
    settings = designed.model_copy(update={"render_timeout_s": timeout})
    job = queue_render(settings, "CH-2034", "A", actor="tester")

    failed = run_job(settings, job["id"], command=fake_blender)

    assert failed["status"] == "failed"
    assert message in failed["error"]
    assert failed["image"] is None
    render_folder = settings.designs_root / "CH-2034" / "A" / "render"
    assert [p.name for p in render_folder.iterdir()] == ["CH-2034_A_gold_plate.log"]
    audit = read_audit(settings.data_dir, sku="CH-2034")[-1]
    assert audit["action"] == "render.failed"
    assert message in audit["details"]["error"]


def test_missing_blender_fails_the_job_with_a_hint(designed: Settings) -> None:
    settings = designed.model_copy(update={"blender_bin": "no-such-blender-binary"})
    job = queue_render(settings, "CH-2034", "A", actor="tester")

    failed = run_job(settings, job["id"])

    assert failed["status"] == "failed"
    assert "set BLENDER_BIN" in failed["error"]


def test_a_deleted_model_fails_the_job(designed: Settings, fake_blender: list[str]) -> None:
    job = queue_render(designed, "GB-1034", "A", actor="tester")
    (designed.designs_root / "GB-1034" / "A" / "GB-1034_A.glb").unlink()

    failed = run_job(designed, job["id"], command=fake_blender)

    assert failed["status"] == "failed"
    assert "GB-1034_A.glb is missing" in failed["error"]


def test_blender_runs_without_a_shell_and_with_factory_settings(settings: Settings) -> None:
    command = blender_command(settings)

    assert command[0] == settings.blender_bin
    assert {"--background", "--factory-startup", "--disable-autoexec"} <= set(command)
    assert command[command.index("--python-exit-code") + 1] == "1"
    assert command[command.index("--python") + 1] == str(BLENDER_SCRIPT)
    assert command[-1] == "--"  # the job file comes after it


def test_restart_fails_interrupted_jobs(designed: Settings) -> None:
    job = queue_render(designed, "CH-2034", "A", actor="tester")
    jobs_module._claim(designed, job["id"])  # the server stopped mid-render

    assert recover_interrupted(designed) == 1

    failed = get_job(designed, job["id"])
    assert failed["status"] == "failed"
    assert "Interrupted" in failed["error"]
    assert _actions(designed, "CH-2034")[-1] == "render.failed"
    assert recover_interrupted(designed) == 0


def test_the_worker_renders_queued_jobs_in_order(
    designed: Settings, fake_blender: list[str]
) -> None:
    first = queue_render(designed, "GB-1034", "A", actor="tester")
    second = queue_render(designed, "CH-2034", "A", actor="tester")
    worker = RenderWorker(designed, poll_s=0.05, command=fake_blender)

    def statuses() -> list[str]:
        return [get_job(designed, j["id"])["status"] for j in (first, second)]

    worker.start()
    try:
        deadline = time.monotonic() + 30
        while statuses() != ["done", "done"] and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        worker.stop()

    assert statuses() == ["done", "done"]
    assert not worker.alive
    started = [get_job(designed, j["id"])["started_at"] for j in (first, second)]
    assert started[0] < started[1]


def test_cli_render(
    designed: Settings,
    fake_blender: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("app.cli.get_settings", lambda: designed)
    monkeypatch.setattr(jobs_module, "blender_command", lambda settings: fake_blender)

    assert main(["render", "--sku", "CH-2034", "--rev", "A", "--finish", "antique_bronze"]) == 0
    assert "CH-2034_A_antique_bronze.png" in capsys.readouterr().out
    assert main(["render", "--sku", "CH-2034", "--rev", "A", "--finish", "honey"]) == 2
    assert "CH-05" in capsys.readouterr().err
    assert _actions(designed, "CH-2034")[-2:] == ["render.queued", "render.done"]
