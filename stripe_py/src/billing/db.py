"""DynamoDB wrapper for the datasheetminer-users table.

Mirrors stripe/src/db.rs. boto3 client is memoised at module scope so
warm Lambda invokes reuse the connection.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import boto3

from .models import SubscriptionStatus, UserRecord


@lru_cache(maxsize=1)
def _default_client():
    return boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))


class UsersDb:
    def __init__(self, table_name: str, client: Any | None = None) -> None:
        self.table_name = table_name
        self.client = client or _default_client()

    def get_user(self, user_id: str) -> UserRecord | None:
        resp = self.client.get_item(
            TableName=self.table_name,
            Key={"user_id": {"S": user_id}},
        )
        item = resp.get("Item")
        return _record_from_item(item) if item else None

    def get_user_by_customer_id(self, customer_id: str) -> UserRecord | None:
        # TODO: add a GSI on stripe_customer_id when user count > ~5k.
        resp = self.client.scan(
            TableName=self.table_name,
            FilterExpression="stripe_customer_id = :cid",
            ExpressionAttributeValues={":cid": {"S": customer_id}},
        )
        items = resp.get("Items") or []
        return _record_from_item(items[0]) if items else None

    def put_user(self, record: UserRecord) -> None:
        item: dict[str, Any] = {
            "user_id": {"S": record.user_id},
            "stripe_customer_id": {"S": record.stripe_customer_id},
            "subscription_status": {"S": record.subscription_status.value},
            "created_at": {"S": record.created_at},
        }
        if record.subscription_id:
            item["subscription_id"] = {"S": record.subscription_id}
        self.client.put_item(TableName=self.table_name, Item=item)

    def update_subscription_status(
        self,
        user_id: str,
        subscription_id: str,
        status: SubscriptionStatus,
    ) -> None:
        self.client.update_item(
            TableName=self.table_name,
            Key={"user_id": {"S": user_id}},
            UpdateExpression="SET subscription_id = :sid, subscription_status = :status",
            ExpressionAttributeValues={
                ":sid": {"S": subscription_id},
                ":status": {"S": status.value},
            },
        )


def _record_from_item(item: dict[str, Any]) -> UserRecord:
    def get_s(key: str, default: str | None = None) -> str | None:
        v = item.get(key)
        return v.get("S") if v else default

    return UserRecord(
        user_id=get_s("user_id") or "",
        stripe_customer_id=get_s("stripe_customer_id") or "",
        subscription_id=get_s("subscription_id"),
        subscription_status=SubscriptionStatus.from_str(get_s("subscription_status")),
        created_at=get_s("created_at") or "",
    )
