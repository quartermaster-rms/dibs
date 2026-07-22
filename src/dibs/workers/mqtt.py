"""Optional MQTT-over-TLS desired-state publisher. Fully implemented and dormant
until an MQTT endpoint is configured; polling remains the mandatory fallback."""

from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.parse import urlparse

from ..config import Settings


class MqttPublisher:
    def __init__(self, settings: Settings) -> None:
        self.url = settings.mqtt_url
        self.prefix = settings.mqtt_topic_prefix
        self.tls_ca = settings.mqtt_tls_ca
        self._client: Any = None

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def connect(self) -> None:  # pragma: no cover - requires a live broker
        if not self.enabled:
            return
        import paho.mqtt.client as mqtt

        parsed = urlparse(self.url)
        client = mqtt.Client()
        if self.tls_ca:
            client.tls_set(ca_certs=self.tls_ca)
        client.connect(str(parsed.hostname), parsed.port or 8883)
        client.loop_start()
        self._client = client

    def publish_state(self, node_id: uuid.UUID, enabled: bool) -> None:
        if self._client is None:
            return
        topic = f"{self.prefix}/{node_id}/desired"
        self._client.publish(topic, json.dumps({"enabled": enabled}), qos=1, retain=True)

    def disconnect(self) -> None:  # pragma: no cover - requires a live broker
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
