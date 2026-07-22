"""The authenticated caller's identity and coarse Keycloak roles (README §2)."""

from __future__ import annotations

from dataclasses import dataclass

SYSADMIN = "sysadmin"
ADMIN_DIBS = "admin-dibs"
GROUP_PREFIX = "group-"


@dataclass(frozen=True)
class Identity:
    subject: str
    display_name: str
    email: str
    groups: tuple[str, ...]

    @property
    def is_sysadmin(self) -> bool:
        return SYSADMIN in self.groups

    @property
    def is_app_admin(self) -> bool:
        return ADMIN_DIBS in self.groups

    @property
    def is_admin(self) -> bool:
        """sysadmin or admin-dibs — the full administrative surface."""
        return self.is_sysadmin or self.is_app_admin

    @property
    def department_groups(self) -> tuple[str, ...]:
        return tuple(g for g in self.groups if g.startswith(GROUP_PREFIX))

    def to_dict(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "display_name": self.display_name,
            "email": self.email,
            "groups": list(self.groups),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Identity:
        return cls(
            subject=data["subject"],
            display_name=data.get("display_name", ""),
            email=data.get("email", ""),
            groups=tuple(data.get("groups", [])),
        )
