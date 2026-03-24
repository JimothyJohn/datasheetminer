//! Push subcommand: load JSON file and push to DynamoDB.

use std::path::Path;

use anyhow::Result;
use dsm_db::DynamoClient;
use dsm_models::Product;
use tracing::info;

pub async fn run(file: &Path, table: &str) -> Result<()> {
    let db = DynamoClient::from_env(table).await;

    let content = std::fs::read_to_string(file)?;
    let items: Vec<serde_json::Value> = serde_json::from_str(&content)?;

    let mut products = Vec::new();
    for item in &items {
        match serde_json::from_value::<Product>(item.clone()) {
            Ok(product) => products.push(product),
            Err(e) => tracing::warn!("Skipping invalid item: {}", e),
        }
    }

    info!(
        "Loaded {} valid products from {}",
        products.len(),
        file.display()
    );

    let created = db.batch_create_products(&products).await?;
    info!("Pushed {}/{} products to DynamoDB", created, products.len());

    Ok(())
}
