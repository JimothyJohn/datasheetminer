use hmac::{Hmac, Mac};
use sha2::Sha256;
use tracing::info;

use crate::config::Config;
use crate::db::UsersDb;
use crate::models::SubscriptionStatus;

type HmacSha256 = Hmac<Sha256>;

/// Verify Stripe webhook signature and process the event.
pub async fn handle_webhook(
    config: &Config,
    db: &UsersDb,
    signature_header: &str,
    body: &str,
) -> Result<(), String> {
    verify_signature(&config.stripe_webhook_secret, signature_header, body)?;

    let event: serde_json::Value =
        serde_json::from_str(body).map_err(|e| format!("Invalid JSON: {e}"))?;

    let event_type = event["type"]
        .as_str()
        .ok_or("Missing event type")?;

    info!(event_type, "Processing Stripe webhook");

    match event_type {
        "checkout.session.completed" => {
            let customer_id = event["data"]["object"]["customer"]
                .as_str()
                .ok_or("Missing customer ID")?;
            let subscription_id = event["data"]["object"]["subscription"]
                .as_str()
                .ok_or("Missing subscription ID")?;

            if let Some(user) = db.get_user_by_customer_id(customer_id).await? {
                db.update_subscription_status(
                    &user.user_id,
                    subscription_id,
                    SubscriptionStatus::Active,
                )
                .await?;
                info!(user_id = %user.user_id, "Subscription activated");
            }
        }
        "customer.subscription.updated" | "customer.subscription.deleted" => {
            let customer_id = event["data"]["object"]["customer"]
                .as_str()
                .ok_or("Missing customer ID")?;
            let subscription_id = event["data"]["object"]["id"]
                .as_str()
                .ok_or("Missing subscription ID")?;
            let status_str = event["data"]["object"]["status"]
                .as_str()
                .unwrap_or("none");
            let status = SubscriptionStatus::from(status_str);

            if let Some(user) = db.get_user_by_customer_id(customer_id).await? {
                db.update_subscription_status(
                    &user.user_id,
                    subscription_id,
                    status,
                )
                .await?;
                info!(user_id = %user.user_id, %status_str, "Subscription updated");
            }
        }
        "invoice.payment_failed" => {
            let customer_id = event["data"]["object"]["customer"]
                .as_str()
                .ok_or("Missing customer ID")?;
            if let Some(user) = db.get_user_by_customer_id(customer_id).await? {
                info!(user_id = %user.user_id, "Payment failed");
                // Stripe auto-retries; status change comes via subscription.updated
            }
        }
        _ => {
            info!(event_type, "Ignoring unhandled event type");
        }
    }

    Ok(())
}

/// Verify Stripe-Signature header using HMAC-SHA256.
fn verify_signature(secret: &str, header: &str, payload: &str) -> Result<(), String> {
    // Parse header: t=timestamp,v1=signature
    let mut timestamp = None;
    let mut signature = None;

    for part in header.split(',') {
        let (key, value) = part.split_once('=').ok_or("Malformed signature header")?;
        match key {
            "t" => timestamp = Some(value),
            "v1" => signature = Some(value),
            _ => {}
        }
    }

    let timestamp = timestamp.ok_or("Missing timestamp in signature")?;
    let expected_sig = signature.ok_or("Missing v1 signature")?;

    // Compute expected signature
    let signed_payload = format!("{timestamp}.{payload}");
    let mut mac =
        HmacSha256::new_from_slice(secret.as_bytes()).map_err(|_| "Invalid webhook secret")?;
    mac.update(signed_payload.as_bytes());
    let computed = hex::encode(mac.finalize().into_bytes());

    if computed != expected_sig {
        return Err("Invalid webhook signature".into());
    }

    Ok(())
}
