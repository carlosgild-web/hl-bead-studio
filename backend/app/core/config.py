"""Application settings, read from environment variables (and the repo's `.env`).

Every configurable value lives here; `.env.example` documents the same names.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py -> the repo root is three levels above `app/`.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: Literal["fake", "ollama", "anthropic"] = "fake"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b-instruct-2507"
    # NoDecode: importing CadQuery makes `typing.Union` look like a Sequence to `issubclass`
    # (a side effect of its multimethod dispatch), and pydantic-settings would then try to
    # JSON-decode every `X | None` value read from the environment.
    anthropic_api_key: Annotated[SecretStr | None, NoDecode] = None
    anthropic_model: str = "claude-sonnet-5-5"

    # Mock SAP
    sap_base_url: str = "http://localhost:8100"
    sap_user: str = "demo"
    sap_password: SecretStr = SecretStr("demo")

    # External tools (run as bounded subprocesses, invariant 6)
    freecad_cmd: str = "freecadcmd"
    blender_bin: str = "blender"

    # Renders (decision 0003): one Blender process per job, killed after the timeout
    render_timeout_s: int = Field(default=600, ge=1, le=3600)
    render_samples: int = Field(default=64, ge=1, le=4096)

    # Storage
    data_dir: Path = Path("./data")
    designs_root: Path = Path("./data/designs")

    # Agent
    agent_max_iterations: int = Field(default=6, ge=1, le=20)

    # Online safety (0 = off): requests per minute per client address and route group
    # (chat, actions, preview), model tokens per UTC day, and the age in hours after which
    # generated designs and their renders are deleted.
    rate_limit_per_minute: int = Field(default=30, ge=0, le=10_000)
    daily_token_cap: int = Field(default=0, ge=0)
    designs_retention_hours: float = Field(default=0, ge=0)

    @field_validator("designs_root", "data_dir")
    @classmethod
    def _relative_to_repo(cls, path: Path) -> Path:
        """`./data` means the repo's data folder, whatever the working directory is."""
        return path if path.is_absolute() else REPO_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """The process-wide settings (cached; tests build their own `Settings`)."""
    return Settings()
