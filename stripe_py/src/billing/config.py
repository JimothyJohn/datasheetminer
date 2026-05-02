"""Environment loader and test-mode hard guard.

Mirrors stripe/src/config.rs: required env vars are validated at load
time; refuses to load if STRIPE_SECRET_KEY is not a sk_test_ key. The
Lambda fails to initialise (CloudWatch shows the error) — same UX as
the Rust panic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_id: str
    users_table_name: str
    frontend_url: str

    @property
    def is_test_mode(self) -> bool:
        return self.stripe_secret_key.startswith("sk_test_")


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"{name} must be set")
    return value


def load_config() -> Config:
    config = Config(
        stripe_secret_key=_required("STRIPE_SECRET_KEY"),
        stripe_webhook_secret=_required("STRIPE_WEBHOOK_SECRET"),
        stripe_price_id=_required("STRIPE_PRICE_ID"),
        users_table_name=os.environ.get("USERS_TABLE_NAME", "datasheetminer-users"),
        frontend_url=os.environ.get("FRONTEND_URL", "http://localhost:3000"),
    )
    if not config.is_test_mode:
        raise ConfigError(
            "REFUSING TO START: STRIPE_SECRET_KEY is not a test key. Set sk_test_... to proceed."
        )
    return config
