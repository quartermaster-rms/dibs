"""initial schema

Revision ID: 0001
Revises:
"""
from __future__ import annotations

from alembic import op

from dibs.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # All tables + simple constraints + the partial-unique live-session index.
    Base.metadata.create_all(bind=bind)

    # Calendar exclusivity: no two non-cancelled reservations on one item may
    # overlap on the half-open [starts_at, ends_at) range.
    op.execute(
        """
        ALTER TABLE reservation ADD CONSTRAINT reservation_no_overlap
        EXCLUDE USING gist (
            equipment_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status <> 'cancelled')
        """
    )

    # A node may link only to enable-gated equipment (item AND class
    # requires_enable), enforced continuously on both sides.
    op.execute(
        """
        CREATE FUNCTION dibs_node_requires_gated() RETURNS trigger AS $$
        DECLARE gated boolean;
        BEGIN
            SELECT e.requires_enable AND c.requires_enable INTO gated
            FROM equipment e JOIN equipment_class c ON c.id = e.class_id
            WHERE e.id = NEW.equipment_id;
            IF gated IS NOT TRUE THEN
                RAISE EXCEPTION 'interlock node may only link to enable-gated equipment'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER interlock_node_gated
            BEFORE INSERT OR UPDATE ON interlock_node
            FOR EACH ROW EXECUTE FUNCTION dibs_node_requires_gated();

        CREATE FUNCTION dibs_equipment_keep_gated() RETURNS trigger AS $$
        BEGIN
            IF NEW.requires_enable = false AND OLD.requires_enable = true
               AND EXISTS (SELECT 1 FROM interlock_node n WHERE n.equipment_id = NEW.id) THEN
                RAISE EXCEPTION 'cannot un-gate equipment while interlock nodes are linked'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER equipment_keep_gated
            BEFORE UPDATE ON equipment
            FOR EACH ROW EXECUTE FUNCTION dibs_equipment_keep_gated();

        CREATE FUNCTION dibs_class_keep_gated() RETURNS trigger AS $$
        BEGIN
            IF NEW.requires_enable = false AND OLD.requires_enable = true
               AND EXISTS (
                   SELECT 1 FROM interlock_node n
                   JOIN equipment e ON e.id = n.equipment_id
                   WHERE e.class_id = NEW.id
               ) THEN
                RAISE EXCEPTION 'cannot un-gate class while interlock nodes are linked'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER class_keep_gated
            BEFORE UPDATE ON equipment_class
            FOR EACH ROW EXECUTE FUNCTION dibs_class_keep_gated();
        """
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are forward-only")
