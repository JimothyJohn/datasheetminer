use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub stripe_secret_key: String,
    pub stripe_webhook_secret: String,
    pub stripe_price_id: String,
    pub users_table_name: String,
    pub frontend_url: String,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            stripe_secret_key: env::var("STRIPE_SECRET_KEY")
                .expect("STRIPE_SECRET_KEY must be set"),
            stripe_webhook_secret: env::var("STRIPE_WEBHOOK_SECRET")
                .expect("STRIPE_WEBHOOK_SECRET must be set"),
            stripe_price_id: env::var("STRIPE_PRICE_ID")
                .expect("STRIPE_PRICE_ID must be set"),
            users_table_name: env::var("USERS_TABLE_NAME")
                .unwrap_or_else(|_| "datasheetminer-users".to_string()),
            frontend_url: env::var("FRONTEND_URL")
                .unwrap_or_else(|_| "http://localhost:3000".to_string()),
        }
    }

    pub fn is_test_mode(&self) -> bool {
        self.stripe_secret_key.starts_with("sk_test_")
    }
}
