"""Create the database schema directly from the ORM models.

Tables, indexes (including the partial-unique live-session index) and the simple
constraints come from ``Base.metadata``. The raw DDL below carries the invariants
that cannot be expressed in the metadata — the ``btree_gist`` extension, the GiST
calendar-exclusivity constraint, and the enable-gating triggers. Everything is
idempotent, so this is safe to run against a fresh or an already-provisioned
database. The api container runs it before serving; the tests run it before
pytest.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import Connection

from .db import dispose_engine, get_engine
from .models import Base

_EXTENSION = "CREATE EXTENSION IF NOT EXISTS btree_gist"

# Calendar exclusivity: no two non-cancelled reservations on one item may overlap
# on the half-open [starts_at, ends_at) range.
_EXCLUSION = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'reservation_no_overlap') THEN
        ALTER TABLE reservation ADD CONSTRAINT reservation_no_overlap
            EXCLUDE USING gist (
                equipment_id WITH =,
                tstzrange(starts_at, ends_at, '[)') WITH &&
            ) WHERE (status <> 'cancelled');
    END IF;
END $$;
"""

# An interlock node may link only to enable-gated equipment (item AND class
# requires_enable), enforced continuously on every side that can break it.
_TRIGGERS = """
CREATE OR REPLACE FUNCTION dibs_node_requires_gated() RETURNS trigger AS $$
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

DROP TRIGGER IF EXISTS interlock_node_gated ON interlock_node;
CREATE TRIGGER interlock_node_gated
    BEFORE INSERT OR UPDATE ON interlock_node
    FOR EACH ROW EXECUTE FUNCTION dibs_node_requires_gated();

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

DROP TRIGGER IF EXISTS equipment_keep_gated ON equipment;
CREATE TRIGGER equipment_keep_gated
    BEFORE UPDATE ON equipment
    FOR EACH ROW EXECUTE FUNCTION dibs_equipment_keep_gated();

CREATE OR REPLACE FUNCTION dibs_class_keep_gated() RETURNS trigger AS $$
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

DROP TRIGGER IF EXISTS class_keep_gated ON equipment_class;
CREATE TRIGGER class_keep_gated
    BEFORE UPDATE ON equipment_class
    FOR EACH ROW EXECUTE FUNCTION dibs_class_keep_gated();
"""


def _apply(conn: Connection) -> None:
    conn.exec_driver_sql(_EXTENSION)
    Base.metadata.create_all(conn)
    conn.exec_driver_sql(_EXCLUSION)
    conn.exec_driver_sql(_TRIGGERS)


async def create_schema() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(_apply)
    await dispose_engine()


def main() -> None:
    if sys.platform == "win32":
        # psycopg async requires a selector loop; the default on Windows is Proactor.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(create_schema())


if __name__ == "__main__":
    main()
