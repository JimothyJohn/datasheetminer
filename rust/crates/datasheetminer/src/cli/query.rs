//! Query subcommand: inspect DynamoDB contents.

use anyhow::Result;
use dsm_db::DynamoClient;
use dsm_models::ProductType;
use tracing::info;

pub async fn run(
    table: &str,
    summary: bool,
    list: bool,
    get: Option<String>,
    product_type: &str,
    limit: i32,
    details: bool,
) -> Result<()> {
    let db = DynamoClient::from_env(table).await;

    if summary {
        let s = db.get_summary().await?;
        println!("{}", serde_json::to_string_pretty(&s)?);
        return Ok(());
    }

    if let Some(id) = get {
        let pt = parse_product_type(product_type)?;
        match db.read_product(&id, pt).await? {
            Some(product) => println!("{}", serde_json::to_string_pretty(&product)?),
            None => println!("Not found: {}", id),
        }
        return Ok(());
    }

    if list || product_type != "all" {
        let pt = if product_type == "all" {
            None
        } else {
            Some(parse_product_type(product_type)?)
        };
        let products = db.list_products(pt, Some(limit)).await?;
        info!("Found {} products", products.len());

        if details {
            println!("{}", serde_json::to_string_pretty(&products)?);
        } else {
            for p in &products {
                let base = p.base();
                println!(
                    "{}\t{}\t{}\t{}",
                    base.product_id,
                    p.product_type(),
                    base.manufacturer.as_deref().unwrap_or("N/A"),
                    base.product_name,
                );
            }
        }
    }

    Ok(())
}

fn parse_product_type(s: &str) -> Result<ProductType> {
    match s {
        "motor" => Ok(ProductType::Motor),
        "drive" => Ok(ProductType::Drive),
        "gearhead" => Ok(ProductType::Gearhead),
        "robot_arm" => Ok(ProductType::RobotArm),
        _ => anyhow::bail!("Unknown product type: {}", s),
    }
}
