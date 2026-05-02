"""Report token usage for a user's metered subscription."""

from __future__ import annotations

import time

import stripe

from .config import Config
from .db import UsersDb
from .models import SubscriptionStatus, UsageRequest, UsageResponse


class UsageError(RuntimeError):
    pass


def report_usage(
    config: Config,
    db: UsersDb,
    request: UsageRequest,
) -> UsageResponse:
    total_tokens = request.input_tokens + request.output_tokens
    if total_tokens == 0:
        return UsageResponse(total_tokens=0, recorded=False)

    user = db.get_user(request.user_id)
    if not user:
        raise UsageError("User not found")
    if user.subscription_status != SubscriptionStatus.ACTIVE:
        raise UsageError("User does not have an active subscription")
    if not user.subscription_id:
        raise UsageError("User has no subscription ID")

    subscription = stripe.Subscription.retrieve(
        user.subscription_id,
        api_key=config.stripe_secret_key,
    )
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        raise UsageError("No subscription items found")
    sub_item_id = items[0]["id"]

    # stripe-python ≥10 dropped the SubscriptionItem.create_usage_record helper
    # but the underlying legacy metered-billing endpoint is still served by
    # Stripe and is what the existing Dashboard product is configured for.
    # raw_request lets us call it without pinning the SDK to a 2-year-old line.
    client = stripe.StripeClient(config.stripe_secret_key)
    client.raw_request(
        "post",
        f"/v1/subscription_items/{sub_item_id}/usage_records",
        quantity=total_tokens,
        timestamp=int(time.time()),
    )
    return UsageResponse(total_tokens=total_tokens, recorded=True)
