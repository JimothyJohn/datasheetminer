//! HTML content retrieval with browser-like headers.

use tracing::info;

use crate::ScraperError;

const USER_AGENT: &str =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0";

/// Retrieve HTML content from a webpage.
pub async fn get_web_content(url: &str) -> Result<String, ScraperError> {
    info!("Fetching web content from: {}", url);

    let client = reqwest::Client::new();
    let resp = client
        .get(url)
        .header("User-Agent", USER_AGENT)
        .header(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        .header("Accept-Language", "en-US,en;q=0.5")
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await?;

    let html = resp.text().await?;
    info!("Retrieved {} characters of HTML content", html.len());
    Ok(html)
}
