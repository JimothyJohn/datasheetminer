from __future__ import annotations

import pytest
from pydantic import ValidationError

from billing.models import (
    CheckoutRequest,
    SubscriptionStatus,
    UsageRequest,
    UserRecord,
)


def test_subscription_status_aliases():
    assert SubscriptionStatus.from_str("active") == SubscriptionStatus.ACTIVE
    assert SubscriptionStatus.from_str("cancelled") == SubscriptionStatus.CANCELED
    assert SubscriptionStatus.from_str("canceled") == SubscriptionStatus.CANCELED
    assert SubscriptionStatus.from_str("past_due") == SubscriptionStatus.PAST_DUE
    assert SubscriptionStatus.from_str("incomplete") == SubscriptionStatus.INCOMPLETE
    assert SubscriptionStatus.from_str(None) == SubscriptionStatus.NONE
    assert SubscriptionStatus.from_str("garbage") == SubscriptionStatus.NONE


def test_checkout_request_minimal():
    req = CheckoutRequest.model_validate({"user_id": "u-1"})
    assert req.user_id == "u-1"
    assert req.email is None


def test_usage_request_rejects_negative():
    with pytest.raises(ValidationError):
        UsageRequest.model_validate({"user_id": "u-1", "input_tokens": -5})


def test_usage_request_defaults_to_zero():
    req = UsageRequest.model_validate({"user_id": "u-1"})
    assert req.input_tokens == 0
    assert req.output_tokens == 0


def test_user_record_default_status():
    r = UserRecord(
        user_id="u-1",
        stripe_customer_id="cus_1",
        created_at="2026-05-02T00:00:00Z",
    )
    assert r.subscription_status == SubscriptionStatus.NONE
