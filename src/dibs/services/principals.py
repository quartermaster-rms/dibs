"""The local directory cache: identity captured from each caller's token on
login. Backs the People directory and grant rosters; dibs never queries the
external directory."""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.identity import Identity
from ..models import Principal
from ..timeutil import now_utc


async def upsert_principal(session: AsyncSession, identity: Identity) -> None:
    now = now_utc()
    values = {
        "subject": identity.subject,
        "display_name": identity.display_name,
        "email": identity.email,
        "groups": list(identity.groups),
        "is_admin": identity.is_admin,
        "last_seen_at": now,
    }
    stmt = insert(Principal).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Principal.subject],
        set_={
            "display_name": stmt.excluded.display_name,
            "email": stmt.excluded.email,
            "groups": stmt.excluded.groups,
            "is_admin": stmt.excluded.is_admin,
            "last_seen_at": stmt.excluded.last_seen_at,
        },
    )
    await session.execute(stmt)
