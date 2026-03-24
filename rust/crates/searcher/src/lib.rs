//! Datasheet search via DuckDuckGo and Brave APIs.

pub mod brave;
pub mod duckduckgo;
pub mod filter;

use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum SearchError {
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("Parse error: {0}")]
    Parse(String),
}

/// A single search result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub url: String,
    pub title: String,
    pub snippet: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manufacturer: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub product_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pages: Option<String>,
    #[serde(default)]
    pub quality_score: f64,
}

/// Search API backend selection.
#[derive(Debug, Clone, Copy)]
pub enum SearchApi {
    DuckDuckGo,
    Brave,
}

impl SearchApi {
    pub fn parse(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "brave" => Self::Brave,
            _ => Self::DuckDuckGo,
        }
    }
}

/// Main search function.
pub async fn search_for_products(
    query: &str,
    api: SearchApi,
    api_key: Option<&str>,
    max_results: usize,
) -> Result<Vec<SearchResult>, SearchError> {
    let raw_results = match api {
        SearchApi::DuckDuckGo => duckduckgo::search(query, max_results).await?,
        SearchApi::Brave => {
            let key = api_key.ok_or(SearchError::Parse("Brave API key required".into()))?;
            brave::search(query, key, max_results).await?
        }
    };

    Ok(filter::filter_and_enrich(raw_results))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_search_api_from_str() {
        assert!(matches!(SearchApi::parse("brave"), SearchApi::Brave));
        assert!(matches!(
            SearchApi::parse("duckduckgo"),
            SearchApi::DuckDuckGo
        ));
        assert!(matches!(SearchApi::parse("unknown"), SearchApi::DuckDuckGo));
    }
}
