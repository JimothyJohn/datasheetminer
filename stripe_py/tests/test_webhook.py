from __future__ import annotations

from datetime import UTC, datetime

import pytest
import stripe

from billing.config import load_config
from billing.models import SubscriptionStatus, UserRecord
from billing.webhook import WebhookError, handle_webhook


def _seed_user(db, customer_id: str = "cus_w", user_id: str = "user-w") -> None:
    db.put_user(
        UserRecord(
            user_id=user_id,
            stripe_customer_id=customer_id,
            subscription_status=SubscriptionStatus.NONE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )


def test_invalid_signature_rejected(db, mocker):
    mocker.patch(
        "stripe.Webhook.construct_event",
        side_effect=stripe.SignatureVerificationError("bad sig", "sig", "body"),
    )
    with pytest.raises(WebhookError, match="Invalid signature"):
        handle_webhook(load_config(), db, "t=1,v1=bad", "{}")


def test_checkout_completed_activates(db, mocker):
    _seed_user(db, customer_id="cus_w", user_id="user-w")
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={
            "type": "checkout.session.completed",
            "data": {"object": {"customer": "cus_w", "subscription": "sub_new"}},
        },
    )
    handle_webhook(load_config(), db, "sig", "{}")
    fetched = db.get_user("user-w")
    assert fetched.subscription_status == SubscriptionStatus.ACTIVE
    assert fetched.subscription_id == "sub_new"


def test_subscription_updated_status_change(db, mocker):
    _seed_user(db, customer_id="cus_u", user_id="user-u")
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={
            "type": "customer.subscription.updated",
            "data": {"object": {"customer": "cus_u", "id": "sub_u", "status": "past_due"}},
        },
    )
    handle_webhook(load_config(), db, "sig", "{}")
    fetched = db.get_user("user-u")
    assert fetched.subscription_status == SubscriptionStatus.PAST_DUE
    assert fetched.subscription_id == "sub_u"


def test_subscription_deleted_marks_canceled(db, mocker):
    _seed_user(db, customer_id="cus_d", user_id="user-d")
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_d", "id": "sub_d", "status": "canceled"}},
        },
    )
    handle_webhook(load_config(), db, "sig", "{}")
    fetched = db.get_user("user-d")
    assert fetched.subscription_status == SubscriptionStatus.CANCELED


def test_payment_failed_does_not_change_state(db, mocker):
    _seed_user(db, customer_id="cus_p", user_id="user-p")
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": "cus_p"}},
        },
    )
    handle_webhook(load_config(), db, "sig", "{}")
    fetched = db.get_user("user-p")
    assert fetched.subscription_status == SubscriptionStatus.NONE


def test_unknown_event_ignored(db, mocker):
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={"type": "customer.created", "data": {"object": {}}},
    )
    handle_webhook(load_config(), db, "sig", "{}")  # no exception


def test_missing_customer_in_checkout_event(db, mocker):
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={
            "type": "checkout.session.completed",
            "data": {"object": {"subscription": "sub_x"}},
        },
    )
    with pytest.raises(WebhookError, match="missing customer"):
        handle_webhook(load_config(), db, "sig", "{}")


def test_event_for_unknown_customer_is_silent(db, mocker):
    # No user with cus_ghost in DB → handler logs and returns cleanly.
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={
            "type": "checkout.session.completed",
            "data": {"object": {"customer": "cus_ghost", "subscription": "sub_g"}},
        },
    )
    handle_webhook(load_config(), db, "sig", "{}")  # no exception, no DB row
