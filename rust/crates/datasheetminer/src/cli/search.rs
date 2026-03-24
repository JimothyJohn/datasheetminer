//! Search subcommand: discover datasheets via search engines.

use std::path::PathBuf;

use anyhow::Result;
use dsm_searcher::{search_for_products, SearchApi};
use tracing::info;

pub async fn run(
    product_type: &str,
    query_terms: &[String],
    api: &str,
    api_key: Option<&str>,
    output: &PathBuf,
    append: bool,
    max_results: usize,
) -> Result<()> {
    let search_api = SearchApi::parse(api);
    let query = format!(
        "{} {} datasheet specifications",
        product_type,
        query_terms.join(" ")
    );

    info!("Searching for: {}", query);

    let results = search_for_products(&query, search_api, api_key, max_results).await?;
    info!("Found {} results", results.len());

    // Load existing results if appending
    let mut all_results: Vec<serde_json::Value> = if append && output.exists() {
        let content = std::fs::read_to_string(output)?;
        serde_json::from_str(&content).unwrap_or_default()
    } else {
        Vec::new()
    };

    // Add new results
    for result in &results {
        all_results.push(serde_json::to_value(result)?);
    }

    // Write output
    let json = serde_json::to_string_pretty(&all_results)?;
    std::fs::write(output, &json)?;
    info!(
        "Saved {} results to {}",
        all_results.len(),
        output.display()
    );

    Ok(())
}
