"""Mock SAP settings, read from environment variables (and the repo's `.env`).

The mock accepts the same `SAP_USER` / `SAP_PASSWORD` that the backend's SapClient sends.
`.env.example` documents every name.
"""

from datetime import date
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# sap-mock/app/config.py -> the repo root is two levels above `app/`.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # Basic auth credentials the mock accepts.
    sap_user: str = "demo"
    sap_password: SecretStr = SecretStr("demo")

    # The SQLite file is DATA_DIR/sap_mock.db (created and seeded on first start).
    data_dir: Path = Path("./data")

    # Pins the date SAP writes on new materials (tests, reproducible demos). Empty: today.
    sap_today: date | None = None

    # Chaos switches for the demo: latency, random 503s, maintenance window.
    sap_latency_ms: int = Field(default=0, ge=0, le=60_000)
    sap_fail_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    sap_maintenance: bool = False

    @field_validator("data_dir")
    @classmethod
    def _relative_to_repo(cls, path: Path) -> Path:
        """`./data` means the repo's data folder, whatever the working directory is."""
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sap_mock.db"

    def today(self) -> date:
        """The date SAP writes on new materials: `SAP_TODAY` if set, otherwise today."""
        return self.sap_today or date.today()
