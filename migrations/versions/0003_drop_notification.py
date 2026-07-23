"""drop the notification table

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notification")


def downgrade() -> None:
    raise NotImplementedError("migrations are forward-only")
