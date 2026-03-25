use serde::{Deserialize, Serialize};

/// Stored in DynamoDB: maps user_id to Stripe billing state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserRecord {
    pub user_id: String,
    pub stripe_customer_id: String,
    pub subscription_id: Option<String>,
    pub subscription_status: SubscriptionStatus,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum SubscriptionStatus {
    Active,
    PastDue,
    Canceled,
    Incomplete,
    None,
}

impl From<&str> for SubscriptionStatus {
    fn from(s: &str) -> Self {
        match s {
            "active" => Self::Active,
            "past_due" => Self::PastDue,
            "canceled" | "cancelled" => Self::Canceled,
            "incomplete" => Self::Incomplete,
            _ => Self::None,
        }
    }
}

// --- Request / Response types ---

#[derive(Debug, Deserialize)]
pub struct CheckoutRequest {
    pub user_id: String,
    pub email: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct CheckoutResponse {
    pub checkout_url: String,
}

#[derive(Debug, Deserialize)]
pub struct UsageRequest {
    pub user_id: String,
    pub input_tokens: u64,
    pub output_tokens: u64,
}

#[derive(Debug, Serialize)]
pub struct UsageResponse {
    pub total_tokens: u64,
    pub recorded: bool,
}

#[derive(Debug, Serialize)]
pub struct StatusResponse {
    pub user_id: String,
    pub subscription_status: SubscriptionStatus,
    pub stripe_customer_id: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: String,
}
