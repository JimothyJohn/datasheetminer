use stripe::{Client, CreateUsageRecord, UsageRecord};

use crate::db::UsersDb;
use crate::models::{SubscriptionStatus, UsageRequest, UsageResponse};

/// Report token usage to Stripe for a user's metered subscription.
/// Called internally after each CLI API call completes.
pub async fn report_usage(
    db: &UsersDb,
    stripe_client: &Client,
    req: UsageRequest,
) -> Result<UsageResponse, String> {
    let total_tokens = req.input_tokens + req.output_tokens;
    if total_tokens == 0 {
        return Ok(UsageResponse {
            total_tokens: 0,
            recorded: false,
        });
    }

    // Look up user's subscription
    let user = db
        .get_user(&req.user_id)
        .await?
        .ok_or("User not found")?;

    if user.subscription_status != SubscriptionStatus::Active {
        return Err("User does not have an active subscription".into());
    }

    let subscription_id = user
        .subscription_id
        .ok_or("User has no subscription ID")?;

    // Get the subscription's metered item
    let subscription = stripe::Subscription::retrieve(
        stripe_client,
        &subscription_id.parse().unwrap(),
        &[],
    )
    .await
    .map_err(|e| format!("Stripe subscription retrieve error: {e}"))?;

    let sub_item = subscription
        .items
        .data
        .first()
        .ok_or("No subscription items found")?;

    // Report usage (quantity = total tokens consumed)
    let params = CreateUsageRecord {
        quantity: total_tokens,
        timestamp: Some(chrono::Utc::now().timestamp()),
        ..Default::default()
    };

    UsageRecord::create(stripe_client, &sub_item.id, params)
        .await
        .map_err(|e| format!("Stripe usage record error: {e}"))?;

    Ok(UsageResponse {
        total_tokens,
        recorded: true,
    })
}
