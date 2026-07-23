"""keep interlock nodes on enable-gated equipment across class reassignment

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The original dibs_equipment_keep_gated only fired when an equipment's own
    # requires_enable flipped true->false, missing the case where an equipment
    # carrying interlock nodes is moved to a no-enable class (its effective
    # enable-gating is item.requires_enable AND class.requires_enable). Re-check
    # effective gating on every equipment update instead.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION dibs_equipment_keep_gated() RETURNS trigger AS $$
        DECLARE gated boolean;
        BEGIN
            SELECT NEW.requires_enable AND c.requires_enable INTO gated
            FROM equipment_class c WHERE c.id = NEW.class_id;
            IF gated IS NOT TRUE
               AND EXISTS (SELECT 1 FROM interlock_node n WHERE n.equipment_id = NEW.id) THEN
                RAISE EXCEPTION 'cannot un-gate equipment while interlock nodes are linked'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are forward-only")
