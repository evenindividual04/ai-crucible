"""Database and persistence models for production-grade run tracking."""

from __future__ import annotations

import os
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import SQLModel, Field, Session, create_engine, select
from sqlalchemy import Column, JSON


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    prompt: str
    access_token_hash: str
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
    _ensure_sqlite_compat_columns()


def _ensure_sqlite_compat_columns() -> None:
    """Apply additive SQLite-compatible schema fixes for local dev/test databases."""
    database_url = _database_url()
    if not database_url.startswith("sqlite"):
        return

    with engine.connect() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(runrecord)").fetchall()}
        if "access_token_hash" not in columns:
            conn.exec_driver_sql("ALTER TABLE runrecord ADD COLUMN access_token_hash TEXT NOT NULL DEFAULT ''")

        token_source_column = "access_token" if "access_token" in columns else None
        rows = conn.exec_driver_sql(
            "SELECT id, access_token_hash"
            + (", access_token" if token_source_column else "")
            + " FROM runrecord"
        ).fetchall()

        for row in rows:
            run_id = row[0]
            token_hash = row[1] or ""
            if token_hash:
                continue

            token_value = ""
            if token_source_column:
                token_value = row[2] or ""
            if not token_value:
                token_value = secrets.token_urlsafe(24)

            hashed = hashlib.sha256(token_value.encode("utf-8")).hexdigest()
            conn.exec_driver_sql(
                "UPDATE runrecord SET access_token_hash = :token_hash WHERE id = :run_id",
                {"token_hash": hashed, "run_id": run_id},
            )
            conn.commit()


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
