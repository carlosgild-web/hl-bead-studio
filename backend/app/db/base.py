"""SQLAlchemy engine for the app database `<DATA_DIR>/bead_studio.sqlite3`."""

from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase

DB_FILE = "bead_studio.sqlite3"


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine(data_dir: Path) -> Engine:
    """One engine per data folder; tables are created on first use."""
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{(data_dir / DB_FILE).as_posix()}")
    Base.metadata.create_all(engine)
    return engine
