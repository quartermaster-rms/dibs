"""Runtime policy stored in the ``setting`` table (admin-configured on the
Settings page). All keys have conservative defaults so the app boots usable."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import NotFound
from ..models import QuotaPolicy, Setting

DEFAULTS: dict[str, Any] = {
    # Reservations
    "reservation_slot_granularity_minutes": 15,
    "max_reservation_days_advance": 30,
    # Delegation defaults pre-filled onto new superuser grants (baseline: promote only)
    "delegation_default_can_promote": True,
    "delegation_default_can_grant_superuser": False,
    "delegation_default_can_demote": False,
    # Whether a demote-bearing superuser may demote a peer / itself
    "delegation_allow_peer_demote": False,
    "delegation_allow_self_demote": False,
    # Entity creation defaults
    "default_open_use": False,
    "default_requires_enable": True,
    # Department gate to reach dibs at all (empty = open to all authenticated)
    "dibs_department_groups": [],
    # Interlock device plane
    "node_offline_missed_heartbeats": 3,
    "desired_state_ttl_multiplier": 3,
    "key_rotation_grace_hours": 48,
}


async def get_setting(session: AsyncSession, key: str) -> Any:
    row = await session.get(Setting, key)
    if row is None:
        return DEFAULTS[key]
    return row.value["v"]


async def get_all_settings(session: AsyncSession) -> dict[str, Any]:
    stored = {row.key: row.value["v"] for row in (await session.execute(select(Setting))).scalars()}
    return {**DEFAULTS, **stored}


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    stmt = insert(Setting).values(key=key, value={"v": value})
    stmt = stmt.on_conflict_do_update(
        index_elements=[Setting.key], set_={"value": stmt.excluded.value}
    )
    await session.execute(stmt)


# --- Quota policies (Settings surface) ---


def policy_dict(p: QuotaPolicy) -> dict:
    return {
        "id": str(p.id),
        "quota_type": p.quota_type.value,
        "principal": p.principal,
        "target_kind": p.target_kind.value,
        "target_id": str(p.target_id),
        "window": p.window.value,
        "limit_hours": str(p.limit_hours),
        "hard_cap": p.hard_cap,
        "active": p.active,
    }


async def list_policies(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(select(QuotaPolicy))).scalars()
    return [policy_dict(p) for p in rows]


async def create_policy(session: AsyncSession, **fields: Any) -> QuotaPolicy:
    if "limit_hours" in fields:
        fields["limit_hours"] = Decimal(str(fields["limit_hours"]))
    p = QuotaPolicy(**fields)
    session.add(p)
    await session.flush()
    return p


async def get_policy(session: AsyncSession, policy_id: uuid.UUID) -> QuotaPolicy:
    p = await session.get(QuotaPolicy, policy_id)
    if p is None:
        raise NotFound("quota policy not found")
    return p


async def update_policy(session: AsyncSession, policy_id: uuid.UUID, fields: dict) -> QuotaPolicy:
    p = await get_policy(session, policy_id)
    if "limit_hours" in fields and fields["limit_hours"] is not None:
        fields["limit_hours"] = Decimal(str(fields["limit_hours"]))
    for key, value in fields.items():
        setattr(p, key, value)
    await session.flush()
    return p


async def delete_policy(session: AsyncSession, policy_id: uuid.UUID) -> None:
    p = await get_policy(session, policy_id)
    await session.delete(p)
    await session.flush()
