//! Delete subcommand: remove items from DynamoDB.

use anyhow::Result;
use dsm_db::DynamoClient;
use dsm_models::ProductType;
use tracing::info;

pub async fn run(
    table: &str,
    manufacturer: Option<&str>,
    product_type: Option<&str>,
    _product_name: Option<&str>,
    _product_family: Option<&str>,
    confirm: bool,
    dry_run: bool,
) -> Result<()> {
    if !confirm && !dry_run {
        anyhow::bail!("delete requires --confirm or --dry-run");
    }

    let db = DynamoClient::from_env(table).await;

    // Delete by product type (most targeted)
    if let Some(pt_str) = product_type {
        let pt = match pt_str {
            "motor" => ProductType::Motor,
            "drive" => ProductType::Drive,
            "gearhead" => ProductType::Gearhead,
            "robot_arm" => ProductType::RobotArm,
            _ => anyhow::bail!("Unknown product type: {}", pt_str),
        };

        let count = db.delete_by_product_type(pt, dry_run).await?;
        if dry_run {
            info!("DRY RUN: would delete {} items", count);
        } else {
            info!("Deleted {} items", count);
        }
        return Ok(());
    }

    // Delete all (most destructive)
    if manufacturer.is_none() {
        let count = db.delete_all(dry_run).await?;
        if dry_run {
            info!("DRY RUN: would delete {} items", count);
        } else {
            info!("Deleted {} items", count);
        }
    }

    Ok(())
}
