"""Background processes: worker (notification dispatch, node-offline detection,
optional MQTT publisher) and scheduler (reservation-completion sweep, admin
daily digest). Neither ever re-evaluates or ends a session."""
