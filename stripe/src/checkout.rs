use stripe::{
    CheckoutSession, CheckoutSessionMode, Client, CreateCheckoutSession,
    CreateCheckoutSessionLineItems, CreateCustomer, Customer,
};

use crate::config::Config;
use crate::db::UsersDb;
use crate::models::{CheckoutRequest, CheckoutResponse, SubscriptionStatus, UserRecord};

/// Create a Stripe Checkout session for a metered subscription.
/// If the user already has a Stripe customer, reuse it.
pub async fn create_checkout_session(
    config: &Config,
    db: &UsersDb,
    stripe_client: &Client,
    req: CheckoutRequest,
) -> Result<CheckoutResponse, String> {
    // Guard: refuse if running live keys
    if !config.is_test_mode() {
        return Err("Refusing to create checkout with live keys. Use test keys.".into());
    }

    // Look up or create Stripe customer
    let customer_id = match db.get_user(&req.user_id).await? {
        Some(record) if record.subscription_status == SubscriptionStatus::Active => {
            return Err("User already has an active subscription".into());
        }
        Some(record) => record.stripe_customer_id,
        None => {
            let mut params = CreateCustomer::new();
            params.email = req.email.as_deref();
            params.metadata = Some(
                [("user_id".to_string(), req.user_id.clone())]
                    .into_iter()
                    .collect(),
            );

            let customer = Customer::create(stripe_client, params)
                .await
                .map_err(|e| format!("Stripe create customer error: {e}"))?;

            let record = UserRecord {
                user_id: req.user_id.clone(),
                stripe_customer_id: customer.id.to_string(),
                subscription_id: None,
                subscription_status: SubscriptionStatus::None,
                created_at: chrono::Utc::now().to_rfc3339(),
            };
            db.put_user(&record).await?;

            customer.id.to_string()
        }
    };

    // Build checkout session with metered price
    let mut params = CreateCheckoutSession::new();
    params.mode = Some(CheckoutSessionMode::Subscription);
    params.customer = Some(customer_id.parse().unwrap());
    params.success_url = Some(&config.frontend_url);
    params.cancel_url = Some(&config.frontend_url);
    params.line_items = Some(vec![CreateCheckoutSessionLineItems {
        price: Some(config.stripe_price_id.clone()),
        // No quantity for metered — Stripe bills based on usage records
        ..Default::default()
    }]);

    let session = CheckoutSession::create(stripe_client, params)
        .await
        .map_err(|e| format!("Stripe checkout session error: {e}"))?;

    let url = session.url.ok_or("No checkout URL returned")?;
    Ok(CheckoutResponse { checkout_url: url })
}
