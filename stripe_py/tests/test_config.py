from __future__ import annotations

import pytest

from billing.config import ConfigError, load_config


def test_load_config_success():
    config = load_config()
    assert config.stripe_secret_key == "sk_test_dummy"
    assert config.is_test_mode


def test_refuses_live_keys(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_dangerous")
    with pytest.raises(ConfigError, match="not a test key"):
        load_config()


def test_missing_required_key(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ConfigError, match="STRIPE_WEBHOOK_SECRET must be set"):
        load_config()


def test_defaults_users_table(monkeypatch):
    monkeypatch.delenv("USERS_TABLE_NAME", raising=False)
    config = load_config()
    assert config.users_table_name == "datasheetminer-users"


def test_defaults_frontend_url(monkeypatch):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    config = load_config()
    assert config.frontend_url == "http://localhost:3000"
