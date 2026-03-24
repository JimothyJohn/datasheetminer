//! URL type detection: PDF vs HTML.

use tracing::warn;

/// Check if a URL points to a PDF document.
pub fn is_pdf_url(url: &str) -> bool {
    url.to_lowercase().ends_with(".pdf")
}

/// Async check: try HEAD request to verify Content-Type.
pub async fn is_pdf_url_async(url: &str) -> bool {
    if url.to_lowercase().ends_with(".pdf") {
        return true;
    }

    if url.starts_with("http://") || url.starts_with("https://") {
        let client = reqwest::Client::new();
        match client.head(url).send().await {
            Ok(resp) => {
                if let Some(ct) = resp.headers().get("content-type") {
                    if let Ok(ct_str) = ct.to_str() {
                        return ct_str.contains("application/pdf");
                    }
                }
                false
            }
            Err(e) => {
                warn!("Could not check Content-Type for {}: {}", url, e);
                false
            }
        }
    } else {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pdf_extension() {
        assert!(is_pdf_url("https://example.com/spec.pdf"));
        assert!(is_pdf_url("https://example.com/SPEC.PDF"));
    }

    #[test]
    fn test_html_url() {
        assert!(!is_pdf_url("https://example.com/product-specs"));
        assert!(!is_pdf_url("https://example.com/page.html"));
    }
}
