use aws_sdk_dynamodb::types::AttributeValue;
use aws_sdk_dynamodb::Client;

use crate::models::{SubscriptionStatus, UserRecord};

pub struct UsersDb {
    client: Client,
    table_name: String,
}

impl UsersDb {
    pub fn new(client: Client, table_name: String) -> Self {
        Self { client, table_name }
    }

    pub async fn get_user(&self, user_id: &str) -> Result<Option<UserRecord>, String> {
        let result = self
            .client
            .get_item()
            .table_name(&self.table_name)
            .key("user_id", AttributeValue::S(user_id.to_string()))
            .send()
            .await
            .map_err(|e| format!("DynamoDB get error: {e}"))?;

        match result.item {
            Some(item) => Ok(Some(record_from_item(&item)?)),
            None => Ok(None),
        }
    }

    pub async fn get_user_by_customer_id(
        &self,
        customer_id: &str,
    ) -> Result<Option<UserRecord>, String> {
        let result = self
            .client
            .scan()
            .table_name(&self.table_name)
            .filter_expression("stripe_customer_id = :cid")
            .expression_attribute_values(
                ":cid",
                AttributeValue::S(customer_id.to_string()),
            )
            .send()
            .await
            .map_err(|e| format!("DynamoDB scan error: {e}"))?;

        match result.items {
            Some(items) if !items.is_empty() => Ok(Some(record_from_item(&items[0])?)),
            _ => Ok(None),
        }
    }

    pub async fn put_user(&self, record: &UserRecord) -> Result<(), String> {
        let mut req = self
            .client
            .put_item()
            .table_name(&self.table_name)
            .item("user_id", AttributeValue::S(record.user_id.clone()))
            .item(
                "stripe_customer_id",
                AttributeValue::S(record.stripe_customer_id.clone()),
            )
            .item(
                "subscription_status",
                AttributeValue::S(
                    serde_json::to_string(&record.subscription_status)
                        .unwrap()
                        .trim_matches('"')
                        .to_string(),
                ),
            )
            .item("created_at", AttributeValue::S(record.created_at.clone()));

        if let Some(ref sub_id) = record.subscription_id {
            req = req.item("subscription_id", AttributeValue::S(sub_id.clone()));
        }

        req.send()
            .await
            .map_err(|e| format!("DynamoDB put error: {e}"))?;
        Ok(())
    }

    pub async fn update_subscription_status(
        &self,
        user_id: &str,
        subscription_id: &str,
        status: SubscriptionStatus,
    ) -> Result<(), String> {
        self.client
            .update_item()
            .table_name(&self.table_name)
            .key("user_id", AttributeValue::S(user_id.to_string()))
            .update_expression(
                "SET subscription_id = :sid, subscription_status = :status",
            )
            .expression_attribute_values(
                ":sid",
                AttributeValue::S(subscription_id.to_string()),
            )
            .expression_attribute_values(
                ":status",
                AttributeValue::S(
                    serde_json::to_string(&status)
                        .unwrap()
                        .trim_matches('"')
                        .to_string(),
                ),
            )
            .send()
            .await
            .map_err(|e| format!("DynamoDB update error: {e}"))?;
        Ok(())
    }
}

fn record_from_item(
    item: &std::collections::HashMap<String, AttributeValue>,
) -> Result<UserRecord, String> {
    let get_s = |key: &str| -> Result<String, String> {
        item.get(key)
            .and_then(|v| v.as_s().ok())
            .map(|s| s.to_string())
            .ok_or_else(|| format!("missing field: {key}"))
    };

    Ok(UserRecord {
        user_id: get_s("user_id")?,
        stripe_customer_id: get_s("stripe_customer_id")?,
        subscription_id: item
            .get("subscription_id")
            .and_then(|v| v.as_s().ok())
            .map(|s| s.to_string()),
        subscription_status: get_s("subscription_status")
            .map(|s| SubscriptionStatus::from(s.as_str()))
            .unwrap_or(SubscriptionStatus::None),
        created_at: get_s("created_at")?,
    })
}
