//! Scrape subcommand: extract specs from datasheets via Gemini LLM.

use std::path::PathBuf;

use anyhow::{bail, Result};
use dsm_db::DynamoClient;
use dsm_llm::gemini::{generate_product_id, DocumentContent, ExtractionContext, GeminiClient};
use dsm_models::Product;
use dsm_quality::filter_products;
use dsm_scraper::{is_pdf_url, parse_page_ranges};
use tracing::{error, info, warn};

#[allow(clippy::too_many_arguments)]
pub async fn run(
    product_type: Option<&str>,
    url: Option<&str>,
    pages: Option<&str>,
    manufacturer: Option<&str>,
    product_name: Option<&str>,
    product_family: Option<&str>,
    from_json: Option<&PathBuf>,
    _json_index: usize,
    _scrape_from_db: bool,
    _scrape_all: bool,
    output: &PathBuf,
    api_key: Option<&str>,
    table: &str,
) -> Result<()> {
    let api_key = api_key
        .or_else(|| std::env::var("GEMINI_API_KEY").ok().as_deref().map(|_| ""))
        .ok_or_else(|| anyhow::anyhow!("API key required (--api-key or GEMINI_API_KEY)"))?;

    // Get api key from env if the option was just a placeholder
    let api_key = if api_key.is_empty() {
        std::env::var("GEMINI_API_KEY")?
    } else {
        api_key.to_string()
    };

    let product_type = product_type.ok_or_else(|| anyhow::anyhow!("--product-type required"))?;

    // Determine URL source
    let url = if let Some(json_path) = from_json {
        let content = std::fs::read_to_string(json_path)?;
        let data: serde_json::Value = serde_json::from_str(&content)?;
        data[product_type][0]["url"]
            .as_str()
            .map(|s| s.to_string())
            .ok_or_else(|| anyhow::anyhow!("No URL found in JSON file"))?
    } else {
        url.ok_or_else(|| anyhow::anyhow!("--url required"))?
            .to_string()
    };

    let manufacturer = manufacturer.unwrap_or("Unknown");
    let product_name = product_name.unwrap_or("Unknown");

    let db = DynamoClient::from_env(table).await;
    let gemini = GeminiClient::new(api_key);

    // Check if product already exists
    let pt = match product_type {
        "motor" => dsm_models::ProductType::Motor,
        "drive" => dsm_models::ProductType::Drive,
        "gearhead" => dsm_models::ProductType::Gearhead,
        "robot_arm" => dsm_models::ProductType::RobotArm,
        other => bail!("Unknown product type: {}", other),
    };

    if db.product_exists(pt, manufacturer, product_name).await? {
        warn!(
            "Product '{}' by '{}' already exists. Skipping.",
            product_name, manufacturer
        );
        return Ok(());
    }

    // Retrieve document
    info!("Starting document analysis for: {}", url);
    let is_pdf = is_pdf_url(&url);
    let content_type = if is_pdf { "pdf" } else { "html" };
    info!("Content type detected: {}", content_type);

    let doc = if is_pdf {
        let _page_indices = pages.map(parse_page_ranges).transpose()?;
        let data = dsm_scraper::pdf::get_document(&url, None).await?;
        DocumentContent::Pdf(data)
    } else {
        let html = dsm_scraper::web::get_web_content(&url).await?;
        DocumentContent::Html(html)
    };

    let context = ExtractionContext {
        product_name: Some(product_name.to_string()),
        manufacturer: Some(manufacturer.to_string()),
        product_family: product_family.map(|s| s.to_string()),
        datasheet_url: Some(url.clone()),
    };

    // Call Gemini
    let response_text = gemini.generate_content(doc, Some(&context)).await?;

    // Parse response
    let mut items = gemini.parse_response(&response_text, Some(&context))?;

    // Set product_type on each item
    for item in &mut items {
        if let Some(obj) = item.as_object_mut() {
            obj.insert(
                "product_type".into(),
                serde_json::Value::String(product_type.to_string()),
            );
        }
    }

    // Validate into Product models
    let mut products = Vec::new();
    for item in &items {
        match serde_json::from_value::<Product>(item.clone()) {
            Ok(mut product) => {
                // Generate deterministic ID
                let base = product.base();
                if let Some(id) = generate_product_id(
                    base.manufacturer.as_deref(),
                    base.part_number.as_deref(),
                    Some(&base.product_name),
                ) {
                    product.base_mut().product_id = id;
                }
                products.push(product);
            }
            Err(e) => {
                error!("Failed to validate product: {}", e);
            }
        }
    }

    // Quality filter
    let (products, rejected) = filter_products(products, None);
    if !rejected.is_empty() {
        warn!("Dropped {} low-quality products", rejected.len());
    }

    if products.is_empty() {
        error!("No valid products extracted");
        return Ok(());
    }

    // Save to file
    let json_output = serde_json::to_string_pretty(&products)?;
    std::fs::write(output, &json_output)?;
    info!("Saved {} products to {}", products.len(), output.display());

    // Push to DB
    let created = db.batch_create_products(&products).await?;
    info!("Pushed {}/{} products to DynamoDB", created, products.len());

    Ok(())
}
