//! Shared application state.

use std::sync::Arc;

use dsm_db::DynamoClient;

#[derive(Clone)]
pub struct AppState {
    pub db: Arc<DynamoClient>,
}
