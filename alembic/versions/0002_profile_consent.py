"""Profil roziligi maydoni.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-09 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns() -> set[str] | None:
    if context.is_offline_mode():
        return None
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("users")}


def upgrade() -> None:
    columns = _columns()
    if columns is None or "profile_consent" not in columns:
        op.add_column(
            "users",
            sa.Column("profile_consent", sa.String(length=16), nullable=True),
        )


def downgrade() -> None:
    columns = _columns()
    if columns is None or "profile_consent" in columns:
        op.drop_column("users", "profile_consent")
