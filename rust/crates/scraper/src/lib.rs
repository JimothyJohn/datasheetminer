//! Document retrieval: PDF download, HTML fetching, and URL type detection.

pub mod detect;
pub mod pdf;
pub mod web;

pub use detect::is_pdf_url;

#[derive(Debug, thiserror::Error)]
pub enum ScraperError {
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("PDF error: {0}")]
    Pdf(String),

    #[error("Page range error: {0}")]
    PageRange(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

/// Parsed page range result (0-indexed).
pub fn parse_page_ranges(s: &str) -> Result<Vec<usize>, ScraperError> {
    let mut pages = std::collections::BTreeSet::new();
    for part in s.split(',') {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        if let Some((start_s, end_s)) = part.split_once(':').or_else(|| part.split_once('-')) {
            let start: usize = start_s
                .parse()
                .map_err(|_| ScraperError::PageRange(format!("Invalid range: {}", part)))?;
            let end: usize = end_s
                .parse()
                .map_err(|_| ScraperError::PageRange(format!("Invalid range: {}", part)))?;
            if start > end {
                return Err(ScraperError::PageRange(format!(
                    "Invalid range: {} > {}",
                    start, end
                )));
            }
            // Convert to 0-indexed
            for p in start..=end {
                pages.insert(p.saturating_sub(1));
            }
        } else {
            let p: usize = part
                .parse()
                .map_err(|_| ScraperError::PageRange(format!("Invalid page: {}", part)))?;
            pages.insert(p.saturating_sub(1));
        }
    }
    Ok(pages.into_iter().collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_single_page() {
        assert_eq!(parse_page_ranges("1").unwrap(), vec![0]);
    }

    #[test]
    fn test_parse_comma_separated() {
        assert_eq!(parse_page_ranges("1,3,5").unwrap(), vec![0, 2, 4]);
    }

    #[test]
    fn test_parse_range_colon() {
        assert_eq!(parse_page_ranges("1:5").unwrap(), vec![0, 1, 2, 3, 4]);
    }

    #[test]
    fn test_parse_range_dash() {
        assert_eq!(parse_page_ranges("1-3").unwrap(), vec![0, 1, 2]);
    }

    #[test]
    fn test_parse_mixed() {
        assert_eq!(parse_page_ranges("1,3:5,8").unwrap(), vec![0, 2, 3, 4, 7]);
    }

    #[test]
    fn test_parse_invalid_range() {
        assert!(parse_page_ranges("5-3").is_err());
    }
}
