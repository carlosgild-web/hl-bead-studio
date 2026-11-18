"""Conversations, their messages, agent runs (traces, invariant 7) and pending actions
(the confirmation gate, invariant 2), in the app database."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import (
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
    update,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, get_engine

ACTION_TTL = timedelta(minutes=30)
ACTION_KINDS = ("reserve_sku", "generate_design", "render")
PENDING, EXECUTING, CONFIRMED, FAILED, CANCELLED = (
    "pending",
    "executing",
    "confirmed",
    "failed",
    "cancelled",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    """SQLite hands datetimes back without a zone; they are stored in UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(2), default="en")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(Integer)
    data: Mapped[str] = mapped_column(Text)  # JSON


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="running")
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trace: Mapped[str] = mapped_column(Text, default="{}")  # JSON


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    run_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=PENDING)
    payload: Mapped[str] = mapped_column(Text)  # JSON, validated when the card opened
    result: Mapped[str | None] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@dataclass(frozen=True)
class ActionRecord:
    id: str
    conversation_id: str
    run_id: int | None
    kind: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None

    @property
    def expired(self) -> bool:
        return self.status == PENDING and _now() >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "kind": self.kind,
            "status": "expired" if self.expired else self.status,
            "payload": self.payload,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


TABLES = (Conversation, ConversationMessage, AgentRun, PendingAction)


@lru_cache
def _engine(data_dir: Path) -> Engine:
    """The app database, with these tables created even if the engine already existed."""
    engine = get_engine(data_dir)
    for table in TABLES:
        table.__table__.create(engine, checkfirst=True)
    return engine


def _record(row: PendingAction) -> ActionRecord:
    return ActionRecord(
        id=row.id,
        conversation_id=row.conversation_id,
        run_id=row.run_id,
        kind=row.kind,
        status=row.status,
        payload=json.loads(row.payload),
        result=json.loads(row.result) if row.result else None,
        created_at=_aware(row.created_at),
        expires_at=_aware(row.expires_at),
        decided_at=_aware(row.decided_at) if row.decided_at else None,
    )


class Store:
    """All reads and writes of the agent tables, for one data folder."""

    def __init__(self, data_dir: Path) -> None:
        self.engine = _engine(data_dir)

    # --- conversations -----------------------------------------------------------------

    def create_conversation(self, language: str = "en") -> str:
        conversation_id = uuid.uuid4().hex
        with Session(self.engine) as s:
            s.add(Conversation(id=conversation_id, created_at=_now(), language=language))
            s.commit()
        return conversation_id

    def conversation_exists(self, conversation_id: str) -> bool:
        with Session(self.engine) as s:
            return s.get(Conversation, conversation_id) is not None

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]] | None:
        if not self.conversation_exists(conversation_id):
            return None
        query = (
            select(ConversationMessage.data)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id)
        )
        with Session(self.engine) as s:
            return [json.loads(d) for d in s.scalars(query)]

    def append_messages(
        self, conversation_id: str, messages: list[dict[str, Any]], run_id: int | None = None
    ) -> None:
        with Session(self.engine) as s:
            s.add_all(
                ConversationMessage(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    data=json.dumps(m, ensure_ascii=False),
                )
                for m in messages
            )
            s.commit()

    # --- runs ----------------------------------------------------------------------------

    def start_run(self, conversation_id: str, provider: str, model: str) -> int:
        with Session(self.engine) as s:
            run = AgentRun(
                conversation_id=conversation_id,
                provider=provider,
                model=model[:64],
                started_at=_now(),
            )
            s.add(run)
            s.commit()
            return run.id

    def finish_run(
        self, run_id: int, *, status: str, model_calls: int, tokens: int, trace: dict[str, Any]
    ) -> None:
        with Session(self.engine) as s:
            run = s.get(AgentRun, run_id)
            assert run is not None
            run.status, run.model_calls, run.tokens = status, model_calls, tokens
            run.finished_at = _now()
            run.trace = json.dumps(trace, ensure_ascii=False)
            s.commit()

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with Session(self.engine) as s:
            run = s.get(AgentRun, run_id)
            if run is None:
                return None
            return {
                "id": run.id,
                "conversation_id": run.conversation_id,
                "provider": run.provider,
                "model": run.model,
                "status": run.status,
                "model_calls": run.model_calls,
                "tokens": run.tokens,
                "started_at": _aware(run.started_at).isoformat(),
                "finished_at": _aware(run.finished_at).isoformat() if run.finished_at else None,
                "trace": json.loads(run.trace),
            }

    def tokens_since(self, since: datetime) -> int:
        with Session(self.engine) as s:
            total = s.scalar(
                select(func.coalesce(func.sum(AgentRun.tokens), 0)).where(
                    AgentRun.started_at >= since
                )
            )
            return int(total or 0)

    # --- pending actions -----------------------------------------------------------------

    def create_action(
        self,
        conversation_id: str,
        kind: str,
        payload: dict[str, Any],
        run_id: int | None = None,
        ttl: timedelta = ACTION_TTL,
    ) -> ActionRecord:
        if kind not in ACTION_KINDS:
            raise ValueError(f"unknown action kind {kind!r}")
        now = _now()
        row = PendingAction(
            id=uuid.uuid4().hex,
            conversation_id=conversation_id,
            run_id=run_id,
            kind=kind,
            status=PENDING,
            payload=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            created_at=now,
            expires_at=now + ttl,
        )
        with Session(self.engine) as s:
            s.add(row)
            s.commit()
            return _record(row)

    def get_action(self, action_id: str) -> ActionRecord | None:
        with Session(self.engine) as s:
            row = s.get(PendingAction, action_id)
            return _record(row) if row else None

    def list_actions(self, conversation_id: str) -> list[ActionRecord]:
        query = (
            select(PendingAction)
            .where(PendingAction.conversation_id == conversation_id)
            .order_by(PendingAction.created_at)
        )
        with Session(self.engine) as s:
            return [_record(r) for r in s.scalars(query)]

    def claim_action(self, action_id: str, to: str) -> bool:
        """Atomically move a pending, unexpired action to `to`; False if another request
        decided it first or it expired. This is what makes a confirmation happen once."""
        now = _now()
        with Session(self.engine) as s:
            result = s.execute(
                update(PendingAction)
                .where(
                    PendingAction.id == action_id,
                    PendingAction.status == PENDING,
                    PendingAction.expires_at > now,
                )
                .values(status=to, decided_at=now)
            )
            s.commit()
            return result.rowcount == 1

    def finish_action(self, action_id: str, *, status: str, result: dict[str, Any]) -> None:
        with Session(self.engine) as s:
            s.execute(
                update(PendingAction)
                .where(PendingAction.id == action_id)
                .values(status=status, result=json.dumps(result, ensure_ascii=False))
            )
            s.commit()
