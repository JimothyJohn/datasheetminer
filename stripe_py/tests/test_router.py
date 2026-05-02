from __future__ import annotations

from datetime import UTC, datetime

from billing.config import load_config
from billing.models import SubscriptionStatus, UserRecord
from billing.router import dispatch


def test_health(db):
    resp = dispatch(load_config(), db, "GET", "/health", {}, "")
    assert resp.status == 200
    assert resp.body == {"status": "ok", "mode": "test"}


def test_unknown_route_404(db):
    resp = dispatch(load_config(), db, "GET", "/elsewhere", {}, "")
    assert resp.status == 404
    assert resp.body == {"error": "Not found"}


def test_status_for_unknown_user(db):
    resp = dispatch(load_config(), db, "GET", "/status/ghost", {}, "")
    assert resp.status == 200
    assert resp.body["subscription_status"] == "none"
    assert resp.body["stripe_customer_id"] is None


def test_status_for_known_user(db):
    db.put_user(
        UserRecord(
            user_id="u-1",
            stripe_customer_id="cus_1",
            subscription_id="sub_1",
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    resp = dispatch(load_config(), db, "GET", "/status/u-1", {}, "")
    assert resp.status == 200
    assert resp.body["subscription_status"] == "active"
    assert resp.body["stripe_customer_id"] == "cus_1"


def test_checkout_invalid_body_returns_400(db):
    resp = dispatch(load_config(), db, "POST", "/checkout", {}, "{}")
    assert resp.status == 400
    assert "Invalid request" in resp.body["error"]


def test_status_missing_user_id_returns_400(db):
    resp = dispatch(load_config(), db, "GET", "/status/", {}, "")
    assert resp.status == 400


def test_webhook_signature_header_case_insensitive(db, mocker):
    mocker.patch(
        "stripe.Webhook.construct_event",
        return_value={"type": "customer.created", "data": {"object": {}}},
    )
    resp = dispatch(
        load_config(),
        db,
        "POST",
        "/webhook",
        {"Stripe-Signature": "t=1,v1=ok"},
        "{}",
    )
    assert resp.status == 200
    assert resp.body == {"received": True}
