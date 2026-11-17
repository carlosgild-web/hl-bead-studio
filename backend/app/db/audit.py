"""Audit log (invariant 9): every reserved SKU, generated design and render writes a row."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, get_engine


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    action: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str | None] = mapped_column(String(16), index=True)
    rev: Mapped[str | None] = mapped_column(String(4))
    details: Mapped[str] = mapped_column(Text)  # JSON


def write_audit(
    data_dir: Path,
    action: str,
    *,
    actor: str,
    sku: str | None = None,
    rev: str | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    row = AuditLog(
        created_at=datetime.now(UTC),
        action=action,
        actor=actor,
        sku=sku,
        rev=rev,
        details=json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
    )
    with Session(get_engine(data_dir)) as session:
        session.add(row)
        session.commit()
        return row.id


def read_audit(data_dir: Path, sku: str | None = None) -> list[dict[str, Any]]:
    query = select(AuditLog).order_by(AuditLog.id)
    if sku is not None:
        query = query.where(AuditLog.sku == sku)
    with Session(get_engine(data_dir)) as session:
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "action": r.action,
                "actor": r.actor,
                "sku": r.sku,
                "rev": r.rev,
                "details": json.loads(r.details),
            }
            for r in session.scalars(query)
        ]
