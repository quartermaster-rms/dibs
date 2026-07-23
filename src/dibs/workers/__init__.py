"""Background processes: worker (notification dispatch, node-offline detection)
and scheduler (reservation-completion sweep, admin daily digest). Neither ever
re-evaluates or ends a session."""
