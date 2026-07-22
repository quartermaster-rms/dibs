"""Domain enumerations (string-valued; stored as VARCHAR + CHECK)."""

from __future__ import annotations

from enum import StrEnum


class ReservationStatus(StrEnum):
    BOOKED = "booked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EndCause(StrEnum):
    USER = "user"
    ADMIN = "admin"


class QuotaType(StrEnum):
    RESERVE = "reserve"
    USAGE = "usage"


class ScopeKind(StrEnum):
    ITEM = "item"
    CLASS = "class"


class QuotaWindow(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Severity(StrEnum):
    WARNING = "warning"
    FATAL = "fatal"


class IssueStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class FailState(StrEnum):
    FAIL_ENABLED = "fail_enabled"
    FAIL_DISABLED = "fail_disabled"


class Tier(StrEnum):
    NONE = "none"
    USER = "user"
    SUPERUSER = "superuser"


class StatusColor(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
