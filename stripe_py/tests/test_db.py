from __future__ import annotations

from datetime import UTC, datetime

from billing.models import SubscriptionStatus, UserRecord


def _make_record(
    user_id: str = "user-1",
    customer_id: str = "cus_1",
    sub_id: str | None = None,
    status: SubscriptionStatus = SubscriptionStatus.NONE,
) -> UserRecord:
    return UserRecord(
        user_id=user_id,
        stripe_customer_id=customer_id,
        subscription_id=sub_id,
        subscription_status=status,
        created_at=datetime.now(UTC).isoformat(),
    )


def test_get_user_missing_returns_none(db):
    assert db.get_user("nope") is None


def test_put_then_get_roundtrip(db):
    record = _make_record()
    db.put_user(record)
    fetched = db.get_user(record.user_id)
    assert fetched is not None
    assert fetched.user_id == record.user_id
    assert fetched.stripe_customer_id == record.stripe_customer_id
    assert fetched.subscription_status == SubscriptionStatus.NONE
    assert fetched.subscription_id is None


def test_put_with_subscription_id(db):
    record = _make_record(sub_id="sub_existing", status=SubscriptionStatus.ACTIVE)
    db.put_user(record)
    fetched = db.get_user("user-1")
    assert fetched.subscription_id == "sub_existing"
    assert fetched.subscription_status == SubscriptionStatus.ACTIVE


def test_get_user_by_customer_id(db):
    db.put_user(_make_record(customer_id="cus_xyz"))
    fetched = db.get_user_by_customer_id("cus_xyz")
    assert fetched is not None
    assert fetched.user_id == "user-1"


def test_get_user_by_customer_id_missing(db):
    assert db.get_user_by_customer_id("cus_missing") is None


def test_update_subscription_status(db):
    db.put_user(_make_record())
    db.update_subscription_status("user-1", "sub_abc", SubscriptionStatus.ACTIVE)
    fetched = db.get_user("user-1")
    assert fetched.subscription_id == "sub_abc"
    assert fetched.subscription_status == SubscriptionStatus.ACTIVE
