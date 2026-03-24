//! Brave Search API integration.

use serde::Deserialize;
use tracing::info;

use crate::{SearchError, SearchResult};

const BRAVE_API_URL: &str = "https://api.search.brave.com/res/v1/web/search";

#[derive(Deserialize)]
struct BraveResponse {
    web: Option<BraveWeb>,
}

#[derive(Deserialize)]
struct BraveWeb {
    results: Vec<BraveResult>,
}

#[derive(Deserialize)]
struct BraveResult {
    url: String,
    title: String,
    description: Option<String>,
}

pub async fn search(
    query: &str,
    api_key: &str,
    max_results: usize,
) -> Result<Vec<SearchResult>, SearchError> {
    info!("Searching Brave for: {}", query);

    let client = reqwest::Client::new();
    let resp = client
        .get(BRAVE_API_URL)
        .header("X-Subscription-Token", api_key)
        .query(&[("q", query), ("count", &max_results.to_string())])
        .send()
        .await?;

    let body: BraveResponse = resp.json().await?;

    let results: Vec<SearchResult> = body
        .web
        .map(|w| {
            w.results
                .into_iter()
                .take(max_results)
                .map(|r| SearchResult {
                    url: r.url,
                    title: r.title,
                    snippet: r.description.unwrap_or_default(),
                    manufacturer: None,
                    product_name: None,
                    pages: None,
                    quality_score: 0.0,
                })
                .collect()
        })
        .unwrap_or_default();

    info!("Found {} results from Brave", results.len());
    Ok(results)
}
