"""initial run persistence tables

Revision ID: 20260420_0001
Revises: 
Create Date: 2026-04-20 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
import hashlib
import secrets


revision = "20260420_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("runrecord"):
        op.create_table(
            "runrecord",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("prompt", sa.String(), nullable=False),
            sa.Column("access_token_hash", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("mode", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("error", sa.String(), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("grade", sa.String(), nullable=True),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        run_columns = {column["name"] for column in inspector.get_columns("runrecord")}
        if "access_token_hash" not in run_columns:
            with op.batch_alter_table("runrecord") as batch_op:
                batch_op.add_column(sa.Column("access_token_hash", sa.String(), nullable=True))

            legacy_token_column = "access_token" if "access_token" in run_columns else None
            rows = bind.exec_driver_sql(
                "SELECT id, access_token_hash"
                + (", access_token" if legacy_token_column else "")
                + " FROM runrecord"
            ).fetchall()
            for row in rows:
                run_id = row[0]
                current_hash = row[1] or ""
                if current_hash:
                    continue
                legacy_token = row[2] if legacy_token_column else ""
                raw_token = legacy_token or secrets.token_urlsafe(24)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                bind.exec_driver_sql(
                    "UPDATE runrecord SET access_token_hash = :token_hash WHERE id = :run_id",
                    {"token_hash": token_hash, "run_id": run_id},
                )

    if not inspector.has_table("runeventrecord"):
        op.create_table(
            "runeventrecord",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), sa.ForeignKey("runrecord.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    event_indexes = {index["name"] for index in inspector.get_indexes("runeventrecord")}
    index_name = op.f("ix_runeventrecord_run_id")
    if index_name not in event_indexes:
        op.create_index(index_name, "runeventrecord", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_runeventrecord_run_id"), table_name="runeventrecord")
    op.drop_table("runeventrecord")
    op.drop_table("runrecord")
