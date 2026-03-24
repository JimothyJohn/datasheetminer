//! DuckDuckGo HTML search (no API key required).

use regex::Regex;
use tracing::info;

use crate::{SearchError, SearchResult};

const DUCKDUCKGO_URL: &str = "https://html.duckduckgo.com/html/";

pub async fn search(query: &str, max_results: usize) -> Result<Vec<SearchResult>, SearchError> {
    info!("Searching DuckDuckGo for: {}", query);

    let client = reqwest::Client::new();
    let resp = client
        .post(DUCKDUCKGO_URL)
        .header("User-Agent", "Mozilla/5.0")
        .form(&[("q", query)])
        .send()
        .await?;

    let html = resp.text().await?;
    let results = parse_results(&html, max_results);

    info!("Found {} results from DuckDuckGo", results.len());
    Ok(results)
}

fn parse_results(html: &str, max_results: usize) -> Vec<SearchResult> {
    let link_re = Regex::new(r#"class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)"#).unwrap();
    let snippet_re = Regex::new(r#"class="result__snippet"[^>]*>([^<]*)"#).unwrap();

    let links: Vec<_> = link_re.captures_iter(html).collect();
    let snippets: Vec<_> = snippet_re.captures_iter(html).collect();

    let mut results = Vec::new();

    for (i, link_cap) in links.iter().enumerate().take(max_results) {
        let url = decode_ddg_url(&link_cap[1]);
        let title = link_cap[2].trim().to_string();
        let snippet = snippets
            .get(i)
            .map(|s| s[1].trim().to_string())
            .unwrap_or_default();

        // Skip DuckDuckGo internal links
        if url.contains("duckduckgo.com") {
            continue;
        }

        results.push(SearchResult {
            url,
            title,
            snippet,
            manufacturer: None,
            product_name: None,
            pages: None,
            quality_score: 0.0,
        });
    }

    results
}

/// Decode DuckDuckGo redirect URL to get the actual target.
fn decode_ddg_url(url: &str) -> String {
    if let Some(pos) = url.find("uddg=") {
        let encoded = &url[pos + 5..];
        let end = encoded.find('&').unwrap_or(encoded.len());
        let encoded = &encoded[..end];
        urlencoding_decode(encoded)
    } else {
        url.to_string()
    }
}

fn urlencoding_decode(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut chars = s.chars();
    while let Some(c) = chars.next() {
        if c == '%' {
            let hex: String = chars.by_ref().take(2).collect();
            if let Ok(byte) = u8::from_str_radix(&hex, 16) {
                result.push(byte as char);
            }
        } else if c == '+' {
            result.push(' ');
        } else {
            result.push(c);
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_ddg_url_plain() {
        assert_eq!(decode_ddg_url("https://example.com"), "https://example.com");
    }

    #[test]
    fn test_decode_ddg_url_redirect() {
        let url = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fspec.pdf&rut=abc";
        assert_eq!(decode_ddg_url(url), "https://example.com/spec.pdf");
    }
}
