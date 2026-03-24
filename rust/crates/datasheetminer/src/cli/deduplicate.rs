//! Deduplicate subcommand: find and remove duplicate products.

use std::collections::HashMap;

use anyhow::Result;
use dsm_db::DynamoClient;
use tracing::{info, warn};

pub async fn run(table: &str, confirm: bool, dry_run: bool, json_output: bool) -> Result<()> {
    if !confirm && !dry_run {
        anyhow::bail!("dedup requires --confirm or --dry-run");
    }

    let db = DynamoClient::from_env(table).await;
    let products = db.list_products(None, None).await?;

    // Group by (part_number, product_name, manufacturer)
    let mut groups: HashMap<String, Vec<(String, String)>> = HashMap::new();
    for product in &products {
        let base = product.base();
        let key = format!(
            "{}|{}|{}",
            base.part_number.as_deref().unwrap_or(""),
            base.product_name,
            base.manufacturer.as_deref().unwrap_or(""),
        );
        groups
            .entry(key)
            .or_default()
            .push((product.pk(), product.sk()));
    }

    let mut duplicates_found = 0;
    let mut keys_to_delete = Vec::new();

    for (key, items) in &groups {
        if items.len() > 1 {
            duplicates_found += items.len() - 1;
            // Keep the first, delete the rest
            for item in &items[1..] {
                keys_to_delete.push(item.clone());
            }
            if !json_output {
                info!("Duplicate group '{}': {} copies", key, items.len());
            }
        }
    }

    let stats = serde_json::json!({
        "total_items": products.len(),
        "duplicate_groups": groups.values().filter(|v| v.len() > 1).count(),
        "duplicates_found": duplicates_found,
        "duplicates_deleted": if dry_run { 0 } else { duplicates_found },
    });

    if json_output {
        println!("{}", serde_json::to_string_pretty(&stats)?);
    } else {
        info!(
            "Found {} duplicates across {} items",
            duplicates_found,
            products.len()
        );
    }

    if dry_run || keys_to_delete.is_empty() {
        return Ok(());
    }

    let deleted = db.batch_delete(&keys_to_delete).await?;
    warn!("Deleted {} duplicate items", deleted);

    Ok(())
}
