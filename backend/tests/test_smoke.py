"""Phase 0 smoke tests: the app starts, answers its health probe and reads settings."""

from pathlib import Path

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
    assert body["llm_provider"] in {"fake", "ollama", "anthropic"}


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
