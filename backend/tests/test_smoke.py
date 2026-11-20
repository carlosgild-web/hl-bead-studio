"""Phase 0 smoke tests: the app starts, answers its health probe and reads settings."""

from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.core.config import REPO_ROOT, Settings
from app.main import app


def test_health_reports_ok_and_version() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["llm_provider"] in get_args(Settings.model_fields["llm_provider"].annotation)


def test_relative_storage_paths_resolve_from_repo_root() -> None:
    settings = Settings(_env_file=None, data_dir=Path("./data"))

    assert settings.data_dir == REPO_ROOT / "data"
    assert settings.designs_root.is_relative_to(REPO_ROOT)


def test_defaults_need_no_model_or_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ignore whatever the developer's machine has set (for example a real API key).
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "fake"
    assert settings.anthropic_api_key is None


def test_api_key_from_the_environment_parses_after_importing_cadquery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # CadQuery's multimethod dispatch makes typing.Union look like a Sequence, and
    # pydantic-settings then tried to JSON-decode `SecretStr | None` values (config.py).
    import cadquery  # noqa: F401

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-test-not-a-real-key"


def test_the_built_frontend_is_served_behind_the_api(tmp_path: Path) -> None:
    from fastapi import FastAPI

    from app.main import mount_frontend

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>studio</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    assert mount_frontend(app, dist)
    http = TestClient(app)
    assert http.get("/").text == "<html>studio</html>"
    assert http.get("/catalog").text == "<html>studio</html>"  # any view: the app decides
    assert http.get("/assets/app.js").text == "console.log(1)"
    assert http.get("/api/ping").json() == {"ok": True}
    assert http.get("/api/nothing").status_code == 404
    assert "no" not in http.get("/../secret.txt").text


def test_without_a_build_nothing_is_mounted(tmp_path: Path) -> None:
    from fastapi import FastAPI

    from app.main import mount_frontend

    assert mount_frontend(FastAPI(), tmp_path / "missing") is False
