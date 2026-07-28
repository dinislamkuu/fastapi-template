"""начальная таблица service_metadata

Revision ID: 202607280001
Revises:
Create Date: 2026-07-28 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "202607280001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "service_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_service_metadata_key"),
        "service_metadata",
        ["key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_service_metadata_key"), table_name="service_metadata")
    op.drop_table("service_metadata")
