"""SQLite storage for the mock SAP: the material master and its number ranges.

The database is created and seeded from `seed/materials.json` the first time the service
starts; delete the file to reset the demo. A reservation takes the next SKU of the material
type's number range and the next material number in one `BEGIN IMMEDIATE` transaction, so
concurrent requests never get the same number, and a failed reservation consumes nothing.
"""

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SEED_FILE = Path(__file__).resolve().parents[1] / "seed" / "materials.json"

FIRST_REVISION = "A"
NEW_STATUS = "IN_DESIGN"
MATERIAL_MAX = 59_999_999  # end of the finished-goods range (Product Design Manual GEN-04)
COLLECTIONS = ("Permanente", "Coastal Garden", "Amber Hollow")


@dataclass(frozen=True)
class MaterialType:
    code: str
    sku_prefix: str
    last_number: int  # highest SKU number of the range (GB-1999, CH-2999)
    families: tuple[str, ...]


MATERIAL_TYPES = {
    t.code: t
    for t in (
        MaterialType("GLASS_BEAD", "GB", 1999, ("RND", "FAC", "LEN", "RON", "CUS")),
        MaterialType("CHARM", "CH", 2999, ("CRS", "INI", "DSC", "CUS")),
    )
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    sku               TEXT PRIMARY KEY,
    material_number   TEXT NOT NULL UNIQUE,
    description       TEXT NOT NULL,
    material_type     TEXT NOT NULL CHECK (material_type IN ('GLASS_BEAD', 'CHARM')),
    family            TEXT,
    collection        TEXT,
    status            TEXT NOT NULL CHECK (status IN ('IN_DESIGN', 'ACTIVE', 'DISCONTINUED')),
    color             TEXT,
    finish            TEXT,
    main_dimension_mm REAL,
    revision          TEXT NOT NULL,
    created_on        TEXT NOT NULL,
    created_by        TEXT NOT NULL
);
-- SAP number ranges: the last SKU number issued per material type, and the last material
-- number. Counters, not MAX() over materials, so a number is never issued twice.
CREATE TABLE IF NOT EXISTS number_ranges (
    material_type TEXT PRIMARY KEY,
    last_number   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS material_range (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    last_material INTEGER NOT NULL
);
"""

FILTERABLE_COLUMNS = frozenset({"material_type", "status", "family", "collection", "description"})


class ReservationError(Exception):
    """SAP refused to reserve a number; `code` and `message` go to the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Database:
    def __init__(self, path: Path, seed_file: Path = SEED_FILE) -> None:
        self.path = path
        self.seed_file = seed_file

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A connection in autocommit mode; write paths open their own transaction."""
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """`BEGIN IMMEDIATE`: takes the write lock up front, so read-then-write is atomic."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    # --- setup ---------------------------------------------------------------------

    def init(self) -> None:
        """Create the schema and load the seed if the database is empty."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
        with self.transaction() as conn:
            if conn.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0:
                self._seed(conn)

    def _seed(self, conn: sqlite3.Connection) -> None:
        materials = json.loads(self.seed_file.read_text(encoding="utf-8"))["materials"]
        conn.executemany(
            "INSERT INTO materials (sku, material_number, description, material_type, family,"
            " collection, status, color, finish, main_dimension_mm, revision, created_on,"
            " created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    m["Sku"],
                    m["MaterialNumber"],
                    m["Description"],
                    m["MaterialType"],
                    m["Family"],
                    m["Collection"],
                    m["Status"],
                    m["Color"],
                    m["Finish"],
                    m["MainDimensionMm"],
                    m["Revision"],
                    m["CreatedOn"],
                    m["CreatedBy"],
                )
                for m in materials
            ],
        )
        # Seeded numbers are issued numbers: the ranges continue after the highest one.
        for code in MATERIAL_TYPES:
            numbers = [_sku_number(m["Sku"]) for m in materials if m["MaterialType"] == code]
            conn.execute(
                "INSERT INTO number_ranges (material_type, last_number) VALUES (?, ?)",
                (code, max(numbers)),
            )
        conn.execute(
            "INSERT INTO material_range (id, last_material) VALUES (1, ?)",
            (max(int(m["MaterialNumber"]) for m in materials),),
        )

    # --- reads ---------------------------------------------------------------------

    def get_material(self, sku: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM materials WHERE sku = ?", (sku,)).fetchone()

    def list_materials(
        self, filters: Mapping[str, str], top: int | None = None, skip: int = 0
    ) -> list[sqlite3.Row]:
        """Materials ordered by SKU. `filters` maps column -> value (equality, AND)."""
        unknown = set(filters) - FILTERABLE_COLUMNS
        if unknown:
            raise ValueError(f"not filterable: {sorted(unknown)}")
        where = " AND ".join(f"{column} = ?" for column in filters)
        sql = "SELECT * FROM materials" + (f" WHERE {where}" if where else "")
        sql += " ORDER BY sku LIMIT ? OFFSET ?"
        params = [*filters.values(), -1 if top is None else top, skip]
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    # --- writes --------------------------------------------------------------------

    def reserve(
        self,
        material_type: str,
        description: str,
        created_by: str,
        today: date,
        family: str | None = None,
        collection: str | None = None,
    ) -> str:
        """Reserve the next SKU and material number; returns the SKU.

        Raises `ReservationError` before touching a number range, so a refused request
        consumes nothing.
        """
        kind = MATERIAL_TYPES.get(material_type)
        if kind is None:
            raise ReservationError(
                "ZHL_MM/010",
                f"Material type '{material_type}' does not exist. Use one of: "
                + ", ".join(MATERIAL_TYPES),
            )
        if family is not None and family not in kind.families:
            raise ReservationError(
                "ZHL_MM/011",
                f"Family '{family}' is not valid for {material_type}. Use one of: "
                + ", ".join(kind.families),
            )
        if collection is not None and collection not in COLLECTIONS:
            raise ReservationError(
                "ZHL_MM/012",
                f"Collection '{collection}' does not exist. Use one of: " + ", ".join(COLLECTIONS),
            )

        with self.transaction() as conn:
            last = conn.execute(
                "SELECT last_number FROM number_ranges WHERE material_type = ?", (material_type,)
            ).fetchone()["last_number"]
            number = last + 1
            if number > kind.last_number:
                raise ReservationError(
                    "ZHL_MM/013", f"SKU number range for {material_type} is exhausted"
                )
            material = (
                conn.execute("SELECT last_material FROM material_range WHERE id = 1").fetchone()[0]
                + 1
            )
            if material > MATERIAL_MAX:
                raise ReservationError(
                    "ZHL_MM/014", "Material number range for finished goods is exhausted"
                )

            sku = f"{kind.sku_prefix}-{number}"
            conn.execute(
                "UPDATE number_ranges SET last_number = ? WHERE material_type = ?",
                (number, material_type),
            )
            conn.execute("UPDATE material_range SET last_material = ? WHERE id = 1", (material,))
            conn.execute(
                "INSERT INTO materials (sku, material_number, description, material_type,"
                " family, collection, status, revision, created_on, created_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sku,
                    f"{material:018d}",
                    description,
                    material_type,
                    family,
                    collection,
                    NEW_STATUS,
                    FIRST_REVISION,
                    today.isoformat(),
                    created_by,
                ),
            )
        return sku


def _sku_number(sku: str) -> int:
    return int(sku.split("-", 1)[1])
