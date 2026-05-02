from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing.checkout import CheckoutError, create_checkout_session
from billing.config import load_config
from billing.models import CheckoutRequest, SubscriptionStatus, UserRecord


def test_creates_new_customer_and_session(db, mocker):
    config = load_config()
    mocker.patch("stripe.Customer.create", return_value={"id": "cus_new"})
    session_create = mocker.patch(
        "stripe.checkout.Session.create",
        return_value={"url": "https://checkout.stripe.com/c/sess_1", "id": "cs_1"},
    )

    response = create_checkout_session(config, db, CheckoutRequest(user_id="u-1", email="a@b.co"))
    assert response.checkout_url == "https://checkout.stripe.com/c/sess_1"

    fetched = db.get_user("u-1")
    assert fetched is not None
    assert fetched.stripe_customer_id == "cus_new"

    call = session_create.call_args
    assert call.kwargs["customer"] == "cus_new"
    assert call.kwargs["mode"] == "subscription"
    assert call.kwargs["line_items"] == [{"price": "price_dummy"}]


def test_reuses_existing_customer(db, mocker):
    config = load_config()
    db.put_user(
        UserRecord(
            user_id="u-2",
            stripe_customer_id="cus_existing",
            subscription_status=SubscriptionStatus.NONE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    customer_create = mocker.patch("stripe.Customer.create")
    session_create = mocker.patch(
        "stripe.checkout.Session.create",
        return_value={"url": "https://checkout.stripe.com/c/sess_2"},
    )

    create_checkout_session(config, db, CheckoutRequest(user_id="u-2"))
    customer_create.assert_not_called()
    assert session_create.call_args.kwargs["customer"] == "cus_existing"


def test_rejects_already_active(db, mocker):
    config = load_config()
    db.put_user(
        UserRecord(
            user_id="u-3",
            stripe_customer_id="cus_active",
            subscription_id="sub_1",
            subscription_status=SubscriptionStatus.ACTIVE,
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    session_create = mocker.patch("stripe.checkout.Session.create")
    with pytest.raises(CheckoutError, match="already has an active"):
        create_checkout_session(config, db, CheckoutRequest(user_id="u-3"))
    session_create.assert_not_called()


def test_rejects_when_no_url(db, mocker):
    config = load_config()
    mocker.patch("stripe.Customer.create", return_value={"id": "cus_x"})
    mocker.patch("stripe.checkout.Session.create", return_value={"url": None})
    with pytest.raises(CheckoutError, match="No checkout URL"):
        create_checkout_session(config, db, CheckoutRequest(user_id="u-4"))
