//! PDF document download.

use tracing::info;

use crate::ScraperError;

const USER_AGENT: &str =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0";

/// Download a PDF document from a URL.
pub async fn download_pdf(url: &str) -> Result<Vec<u8>, ScraperError> {
    info!("Downloading PDF from: {}", url);

    let client = reqwest::Client::new();
    let resp = client
        .get(url)
        .header("User-Agent", USER_AGENT)
        .header("Accept", "*/*")
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await?;

    let bytes = resp.bytes().await?;
    info!("Downloaded {} bytes", bytes.len());
    Ok(bytes.to_vec())
}

/// Retrieve a document: local file or URL.
pub async fn get_document(url: &str, _pages: Option<&[usize]>) -> Result<Vec<u8>, ScraperError> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        // Local file
        let data = std::fs::read(url)?;
        info!("Read {} bytes from local file: {}", data.len(), url);
        // Page extraction would go here with a PDF library
        return Ok(data);
    }

    let data = download_pdf(url).await?;
    // Page extraction would go here with a PDF library
    Ok(data)
}
