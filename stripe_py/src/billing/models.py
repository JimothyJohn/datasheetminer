"""Pydantic request/response models — JSON shape parity with stripe/src/models.rs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    NONE = "none"

    @classmethod
    def from_str(cls, raw: str | None) -> SubscriptionStatus:
        if raw is None:
            return cls.NONE
        if raw == "cancelled":
            return cls.CANCELED
        try:
            return cls(raw)
        except ValueError:
            return cls.NONE


class UserRecord(BaseModel):
    user_id: str
    stripe_customer_id: str
    subscription_id: str | None = None
    subscription_status: SubscriptionStatus = SubscriptionStatus.NONE
    created_at: str


class CheckoutRequest(BaseModel):
    user_id: str
    email: str | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class UsageRequest(BaseModel):
    user_id: str
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)


class UsageResponse(BaseModel):
    total_tokens: int
    recorded: bool


class StatusResponse(BaseModel):
    user_id: str
    subscription_status: SubscriptionStatus
    stripe_customer_id: str | None = None


class ErrorResponse(BaseModel):
    error: str
