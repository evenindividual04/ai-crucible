"""Database and persistence models for production-grade run tracking."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import Column, JSON


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    prompt: str
    status: str = Field(default="queued")
    mode: str = Field(default="live")  # live | demo
    created_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    score: Optional[float] = None
    grade: Optional[str] = None
    summary_json: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class RunEventRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    event_type: str
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./backend/crucible.db")


def create_db_engine():
    database_url = _database_url()
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


engine = create_db_engine()


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def get_run(run_id: str) -> Optional[RunRecord]:
    with get_session() as session:
        return session.get(RunRecord, run_id)


def list_run_events(run_id: str, limit: int = 200) -> list[RunEventRecord]:
    with get_session() as session:
        statement = (
            select(RunEventRecord)
            .where(RunEventRecord.run_id == run_id)
            .order_by(RunEventRecord.id.desc())
            .limit(limit)
        )
        rows = session.exec(statement).all()
    return list(reversed(rows))
