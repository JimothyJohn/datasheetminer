"""Stripe webhook receiver.

Uses ``stripe.Webhook.construct_event`` for signature verification —
drops the hand-rolled HMAC-SHA256 code in stripe/src/webhook.rs:88.
The SDK handles timestamp tolerance and signature encoding edge cases.
"""

from __future__ import annotations

import logging

import stripe

from .config import Config
from .db import UsersDb
from .models import SubscriptionStatus

log = logging.getLogger(__name__)


class WebhookError(RuntimeError):
    pass


def handle_webhook(
    config: Config,
    db: UsersDb,
    signature_header: str,
    body: str,
) -> None:
    try:
        event = stripe.Webhook.construct_event(
            payload=body,
            sig_header=signature_header,
            secret=config.stripe_webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        raise WebhookError(f"Invalid signature: {e}") from e

    event_type = event["type"]
    obj = event["data"]["object"]
    log.info("Processing Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        customer_id = obj.get("customer")
        subscription_id = obj.get("subscription")
        if not customer_id or not subscription_id:
            raise WebhookError("checkout.session.completed missing customer/subscription")
        user = db.get_user_by_customer_id(customer_id)
        if user:
            db.update_subscription_status(user.user_id, subscription_id, SubscriptionStatus.ACTIVE)
            log.info("Subscription activated for user_id=%s", user.user_id)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = obj.get("customer")
        subscription_id = obj.get("id")
        status_str = obj.get("status", "none")
        if not customer_id or not subscription_id:
            raise WebhookError(f"{event_type} missing customer/subscription id")
        user = db.get_user_by_customer_id(customer_id)
        if user:
            db.update_subscription_status(
                user.user_id, subscription_id, SubscriptionStatus.from_str(status_str)
            )
            log.info("Subscription updated user_id=%s status=%s", user.user_id, status_str)

    elif event_type == "invoice.payment_failed":
        customer_id = obj.get("customer")
        if not customer_id:
            raise WebhookError("invoice.payment_failed missing customer")
        user = db.get_user_by_customer_id(customer_id)
        if user:
            log.info("Payment failed for user_id=%s (Stripe auto-retries)", user.user_id)

    else:
        log.info("Ignoring unhandled event type: %s", event_type)
