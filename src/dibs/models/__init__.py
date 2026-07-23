"""ORM models. Importing this package registers every table on ``Base.metadata``."""

from __future__ import annotations

from .base import Base
from .tables import (
    Audit,
    Equipment,
    EquipmentClass,
    IdempotencyRecord,
    InterlockNode,
    IssuePhoto,
    IssueReport,
    IssueUpdate,
    Location,
    Principal,
    QuotaPolicy,
    Reservation,
    RoleGrant,
    Session,
    Setting,
)

__all__ = [
    "Base",
    "Location",
    "EquipmentClass",
    "Equipment",
    "Reservation",
    "Session",
    "QuotaPolicy",
    "IssueReport",
    "IssueUpdate",
    "IssuePhoto",
    "InterlockNode",
    "Principal",
    "RoleGrant",
    "Setting",
    "Audit",
    "IdempotencyRecord",
]
