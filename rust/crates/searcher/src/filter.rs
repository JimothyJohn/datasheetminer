//! Result filtering, quality scoring, and manufacturer extraction.

use regex::Regex;

use crate::SearchResult;

/// Known manufacturers in the industrial automation space.
const KNOWN_MANUFACTURERS: &[&str] = &[
    "ABB",
    "Siemens",
    "Fanuc",
    "Yaskawa",
    "Mitsubishi",
    "Nidec",
    "Kollmorgen",
    "Delta",
    "Beckhoff",
    "Bosch Rexroth",
    "Parker",
    "Allen-Bradley",
    "Rockwell",
    "Omron",
    "Schneider",
    "SEW-Eurodrive",
    "Lenze",
    "Universal Robots",
    "KUKA",
    "Harmonic Drive",
    "Nabtesco",
    "Sesame",
];

/// URL patterns that indicate a spec/datasheet page.
const SPEC_KEYWORDS: &[&str] = &[
    "datasheet",
    "spec",
    "technical",
    "manual",
    "doc",
    "catalog",
    "brochure",
    "download",
    "pdf",
];

/// Score and enrich search results.
pub fn filter_and_enrich(mut results: Vec<SearchResult>) -> Vec<SearchResult> {
    let model_re = Regex::new(r"\b([A-Z]{2,}[-\s]?\d{2,}[A-Z0-9]*)\b").unwrap();

    for result in &mut results {
        // Score quality
        let mut score = 0.0_f64;

        let url_lower = result.url.to_lowercase();
        if url_lower.ends_with(".pdf") {
            score += 0.5;
        }
        for kw in SPEC_KEYWORDS {
            if url_lower.contains(kw) {
                score += 0.1;
            }
        }

        let text = format!("{} {}", result.title, result.snippet).to_lowercase();
        for kw in SPEC_KEYWORDS {
            if text.contains(kw) {
                score += 0.05;
            }
        }

        result.quality_score = score;

        // Extract manufacturer
        for &mfg in KNOWN_MANUFACTURERS {
            if text.contains(&mfg.to_lowercase()) {
                result.manufacturer = Some(mfg.to_string());
                break;
            }
        }

        // Extract model pattern
        if let Some(cap) = model_re.captures(&format!("{} {}", result.title, result.snippet)) {
            result.product_name = Some(cap[1].to_string());
        }

        // Add pages hint for PDFs
        if url_lower.ends_with(".pdf") {
            result.pages = Some("1-10".to_string());
        }
    }

    // Filter by minimum quality and deduplicate by URL
    let mut seen_urls = std::collections::HashSet::new();
    results.retain(|r| r.quality_score >= 0.1 && seen_urls.insert(r.url.clone()));

    // Sort by quality descending
    results.sort_by(|a, b| b.quality_score.partial_cmp(&a.quality_score).unwrap());

    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_filter_scores_pdf_higher() {
        let results = vec![
            SearchResult {
                url: "https://example.com/spec.pdf".into(),
                title: "Motor Datasheet".into(),
                snippet: "Technical specifications".into(),
                manufacturer: None,
                product_name: None,
                pages: None,
                quality_score: 0.0,
            },
            SearchResult {
                url: "https://example.com/page".into(),
                title: "Product page".into(),
                snippet: "Buy now".into(),
                manufacturer: None,
                product_name: None,
                pages: None,
                quality_score: 0.0,
            },
        ];

        let filtered = filter_and_enrich(results);
        // PDF result should score higher
        assert!(!filtered.is_empty());
        assert!(filtered[0].url.contains(".pdf"));
    }

    #[test]
    fn test_filter_extracts_manufacturer() {
        let results = vec![SearchResult {
            url: "https://example.com/spec.pdf".into(),
            title: "ABB Motor ACS580 Datasheet".into(),
            snippet: "Variable frequency drive".into(),
            manufacturer: None,
            product_name: None,
            pages: None,
            quality_score: 0.0,
        }];

        let filtered = filter_and_enrich(results);
        assert_eq!(filtered[0].manufacturer, Some("ABB".to_string()));
    }

    #[test]
    fn test_filter_deduplicates() {
        let results = vec![
            SearchResult {
                url: "https://example.com/spec.pdf".into(),
                title: "Motor Datasheet".into(),
                snippet: "Specs".into(),
                manufacturer: None,
                product_name: None,
                pages: None,
                quality_score: 0.0,
            },
            SearchResult {
                url: "https://example.com/spec.pdf".into(),
                title: "Motor Datasheet (duplicate)".into(),
                snippet: "Specs again".into(),
                manufacturer: None,
                product_name: None,
                pages: None,
                quality_score: 0.0,
            },
        ];

        let filtered = filter_and_enrich(results);
        assert_eq!(filtered.len(), 1);
    }
}
