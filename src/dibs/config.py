"""Runtime configuration.

Everything here is what dibs needs to *boot and connect*; all runtime-tunable
policy (quotas, limits, permission model, slot granularity) lives in the
database and is set by admins in-app (IMPLEMENTATION-GUIDE §8). The only config
source is the process environment, populated from ``deploy/host.env``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMode = Literal["stub", "oidc"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # --- Connections ---
    database_url: str = Field(default="postgresql+psycopg://dibs:dibs@127.0.0.1:5432/dibs")
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")

    # --- Calendar / locale ---
    platform_tz: str = Field(default="UTC")

    # --- Authentication ---
    # ``stub`` is the hermetic dev/test bypass; it is mutually exclusive with the
    # real OIDC identity settings. Production supplies ``oidc`` in host.env.
    auth_mode: AuthMode = Field(default="oidc")
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_url: str | None = None
    oidc_groups_claim: str = "groups"
    oidc_post_login_redirect: str = "/"
    public_base_url: str | None = None

    # --- Session cookie ---
    session_secret: str = Field(default="insecure-dev-secret-change-me")
    cookie_secure: bool = True
    cookie_domain: str | None = None
    session_ttl_seconds: int = 60 * 60 * 12

    # --- Storage ---
    uploads_dir: str = "/data/uploads"

    # --- Device plane ---
    device_port: int = 8443
    device_tls_cert: str | None = None
    device_tls_key: str | None = None
    device_rate_limit_per_minute: int = 120

    # --- Optional MQTT state publisher (dormant until configured) ---
    mqtt_url: str | None = None
    mqtt_tls_ca: str | None = None
    mqtt_topic_prefix: str = "dibs/nodes"

    # --- Observability ---
    log_level: str = "INFO"
    service_name: str = "dibs"

    # --- Idempotency ---
    idempotency_ttl_seconds: int = 60 * 60 * 24

    # --- Background loops ---
    worker_interval_s: int = 30
    scheduler_interval_s: int = 60

    @property
    def stub_login(self) -> bool:
        return self.auth_mode == "stub"

    @model_validator(mode="after")
    def _check_auth(self) -> Settings:
        oidc_set = any((self.oidc_issuer, self.oidc_client_id, self.oidc_client_secret))
        if self.auth_mode == "stub" and oidc_set:
            raise ValueError("stub login is mutually exclusive with OIDC identity settings")
        if self.auth_mode == "oidc" and not (
            self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret
        ):
            raise ValueError(
                "auth_mode=oidc requires oidc_issuer, oidc_client_id, oidc_client_secret"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
