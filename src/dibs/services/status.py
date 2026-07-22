"""Derived equipment health status (never stored): red if any open fatal, else
yellow if any open warning, else green."""

from __future__ import annotations

from ..enums import StatusColor


def compute_status(open_fatal: int, open_warning: int) -> dict:
    if open_fatal > 0:
        color = StatusColor.RED
    elif open_warning > 0:
        color = StatusColor.YELLOW
    else:
        color = StatusColor.GREEN
    return {"color": color.value, "open_fatal": open_fatal, "open_warning": open_warning}
