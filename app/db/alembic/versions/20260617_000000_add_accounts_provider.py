"""add provider column to accounts for freemodel keys

Revision ID: 20260617_000000_add_accounts_provider
Revises: 20260611_000000_merge_dashboard_guest_and_weekly_useragent_heads
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260617_000000_add_accounts_provider"
down_revision = "20260611_000000_merge_dashboard_guest_and_weekly_useragent_heads"
branch_labels = None
depends_on = None


def _columns(connection: Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(connection)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if not columns:
        return

    with op.batch_alter_table("accounts") as batch_op:
        if "provider" not in columns:
            batch_op.add_column(
                sa.Column(
                    "provider",
                    sa.String(),
                    nullable=False,
                    server_default="openai",
                )
            )
        if "refresh_token_encrypted" in columns:
            batch_op.alter_column(
                "refresh_token_encrypted",
                existing_type=sa.LargeBinary(),
                nullable=True,
            )
        if "id_token_encrypted" in columns:
            batch_op.alter_column(
                "id_token_encrypted",
                existing_type=sa.LargeBinary(),
                nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind, "accounts")
    if not columns:
        return

    with op.batch_alter_table("accounts") as batch_op:
        if "provider" in columns:
            batch_op.drop_column("provider")
        if "refresh_token_encrypted" in columns:
            batch_op.alter_column(
                "refresh_token_encrypted",
                existing_type=sa.LargeBinary(),
                nullable=False,
            )
        if "id_token_encrypted" in columns:
            batch_op.alter_column(
                "id_token_encrypted",
                existing_type=sa.LargeBinary(),
                nullable=False,
            )
