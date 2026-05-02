from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing.config import load_config
from billing.models import SubscriptionStatus, UsageRequest, UserRecord
from billing.usage import UsageError, report_usage


def _active_user(db, user_id: str = "user-u", sub_id: str = "sub_active") -> None:
    db.put_user(
        UserRecord(
            user_id=user_id,
            stripe_customer_id="cus_active",
            subscription_id=sub_id,
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )


def test_zero_tokens_returns_unrecorded(db):
    _active_user(db)
    response = report_usage(load_config(), db, UsageRequest(user_id="user-u"))
    assert response.recorded is False
    assert response.total_tokens == 0


def test_records_usage_for_active_user(db, mocker):
    _active_user(db)
    mocker.patch(
        "stripe.Subscription.retrieve",
        return_value={"items": {"data": [{"id": "si_1"}]}},
    )
    raw_request = mocker.patch("stripe.StripeClient.raw_request")

    response = report_usage(
        load_config(),
        db,
        UsageRequest(user_id="user-u", input_tokens=400, output_tokens=100),
    )
    assert response.recorded is True
    assert response.total_tokens == 500

    raw_request.assert_called_once()
    args, kwargs = raw_request.call_args
    assert args[0] == "post"
    assert args[1] == "/v1/subscription_items/si_1/usage_records"
    assert kwargs["quantity"] == 500
    assert "timestamp" in kwargs


def test_unknown_user_rejected(db):
    with pytest.raises(UsageError, match="User not found"):
        report_usage(load_config(), db, UsageRequest(user_id="ghost", input_tokens=1))


def test_inactive_subscription_rejected(db):
    db.put_user(
        UserRecord(
            user_id="user-i",
            stripe_customer_id="cus_i",
            subscription_status=SubscriptionStatus.NONE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    with pytest.raises(UsageError, match="active subscription"):
        report_usage(load_config(), db, UsageRequest(user_id="user-i", input_tokens=1))


def test_active_user_without_subscription_id_rejected(db):
    db.put_user(
        UserRecord(
            user_id="user-x",
            stripe_customer_id="cus_x",
            subscription_id=None,
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    with pytest.raises(UsageError, match="no subscription ID"):
        report_usage(load_config(), db, UsageRequest(user_id="user-x", input_tokens=1))


def test_subscription_with_no_items_rejected(db, mocker):
    _active_user(db)
    mocker.patch(
        "stripe.Subscription.retrieve",
        return_value={"items": {"data": []}},
    )
    with pytest.raises(UsageError, match="No subscription items"):
        report_usage(load_config(), db, UsageRequest(user_id="user-u", input_tokens=10))
