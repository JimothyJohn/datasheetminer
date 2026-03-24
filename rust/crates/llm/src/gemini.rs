//! Gemini REST API client with retry logic.
//!
//! Calls `POST /v1beta/models/{model}:generateContent` directly since
//! there is no official Rust Gemini SDK.

use std::time::Duration;

use base64::Engine;
use serde::{Deserialize, Serialize};
use tracing::{info, warn};

use crate::error::LlmError;

const GEMINI_API_BASE: &str = "https://generativelanguage.googleapis.com/v1beta/models";
const DEFAULT_MODEL: &str = "gemini-2.5-flash";
const MAX_RETRIES: u32 = 5;
const INITIAL_BACKOFF_SECS: u64 = 4;
const MAX_BACKOFF_SECS: u64 = 60;

const GUARDRAILS: &str = r#"
IMPORTANT EXTRACTION RULES:
- Extract EVERY specification that appears in the document for each product variant.
- If a value exists in the document, you MUST include it. Do NOT leave a field null when the data is present.
- Only leave a field null when the specification is genuinely absent from the document.
- For fields with units, always include the unit exactly as shown (e.g., "2.5;A", "3000;rpm", "0.47;Nm").
- If a spec is listed in a table, extract the exact numeric value and unit from the table cell.
- Pay close attention to footnotes, headers, and sub-tables that may contain additional specs.
- Each row or variant in a selection table is a separate product — extract them all.
"#;

/// Document content to send to Gemini.
pub enum DocumentContent {
    Pdf(Vec<u8>),
    Html(String),
}

/// Context about the product being extracted.
#[derive(Debug, Clone, Serialize)]
pub struct ExtractionContext {
    pub product_name: Option<String>,
    pub manufacturer: Option<String>,
    pub product_family: Option<String>,
    pub datasheet_url: Option<String>,
}

pub struct GeminiClient {
    http: reqwest::Client,
    api_key: String,
    model: String,
}

// Gemini API request/response types
#[derive(Serialize)]
struct GenerateContentRequest {
    contents: Vec<Content>,
    #[serde(rename = "generationConfig")]
    generation_config: GenerationConfig,
}

#[derive(Serialize)]
struct Content {
    parts: Vec<Part>,
}

#[derive(Serialize)]
#[serde(untagged)]
enum Part {
    Text {
        text: String,
    },
    InlineData {
        #[serde(rename = "inlineData")]
        inline_data: InlineData,
    },
}

#[derive(Serialize)]
struct InlineData {
    #[serde(rename = "mimeType")]
    mime_type: String,
    data: String,
}

#[derive(Serialize)]
struct GenerationConfig {
    #[serde(rename = "responseMimeType")]
    response_mime_type: String,
    #[serde(rename = "maxOutputTokens")]
    max_output_tokens: u32,
}

#[derive(Deserialize)]
struct GenerateContentResponse {
    candidates: Option<Vec<Candidate>>,
}

#[derive(Deserialize)]
struct Candidate {
    content: Option<CandidateContent>,
}

#[derive(Deserialize)]
struct CandidateContent {
    parts: Option<Vec<ResponsePart>>,
}

#[derive(Deserialize)]
struct ResponsePart {
    text: Option<String>,
}

impl GeminiClient {
    pub fn new(api_key: String) -> Self {
        Self {
            http: reqwest::Client::new(),
            api_key,
            model: DEFAULT_MODEL.to_string(),
        }
    }

    /// Build the prompt based on context.
    fn build_prompt(&self, context: Option<&ExtractionContext>) -> String {
        match context {
            Some(ctx) => format!(
                r#"You are being presented with a catalog for an industrial product.
The following information is already known:
- Product Name: {}
- Manufacturer: {}
- Product Family: {}
- Datasheet URL: {}

Your task is to identify the individual product versions from the document and extract their key technical specifications as completely as possible.
Do NOT include the product_name, manufacturer, product_family, or datasheet_url in your response.

For any field that requires a value and a unit (e.g., weight, torque, voltage), format it as a single string: "value;unit".
For fields representing a range, use the format: "min-max;unit".
Example: "rated_current": "2.5;A", "rated_voltage": "100-200;V"

Fill in as many fields as possible from the document. Only leave a field null if the specification is truly absent.
Focus only on the fields defined in the response schema.

{}"#,
                ctx.product_name.as_deref().unwrap_or("Unknown"),
                ctx.manufacturer.as_deref().unwrap_or("Unknown"),
                ctx.product_family.as_deref().unwrap_or("Unknown"),
                ctx.datasheet_url.as_deref().unwrap_or(""),
                GUARDRAILS,
            ),
            None => format!(
                r#"You are being presented with a catalog for an industrial product. Identify the individual versions along with their key specifications.

For any field that requires a value and a unit (e.g., weight, torque, voltage), format it as a single string: "value;unit".
For fields representing a range, use the format: "min-max;unit".
Example: "rated_current": "2.5;A", "rated_voltage": "100-200;V"

{}"#,
                GUARDRAILS,
            ),
        }
    }

    /// Call Gemini API with retry logic.
    pub async fn generate_content(
        &self,
        doc: DocumentContent,
        context: Option<&ExtractionContext>,
    ) -> Result<String, LlmError> {
        let prompt = self.build_prompt(context);
        let url = format!(
            "{}/{}:generateContent?key={}",
            GEMINI_API_BASE, self.model, self.api_key
        );

        let parts = match doc {
            DocumentContent::Pdf(data) => {
                info!("Analyzing PDF document ({} bytes)", data.len());
                let b64 = base64::engine::general_purpose::STANDARD.encode(&data);
                vec![
                    Part::InlineData {
                        inline_data: InlineData {
                            mime_type: "application/pdf".into(),
                            data: b64,
                        },
                    },
                    Part::Text { text: prompt },
                ]
            }
            DocumentContent::Html(html) => {
                info!("Analyzing HTML content ({} characters)", html.len());
                vec![Part::Text {
                    text: format!("HTML Content:\n\n{}\n\n{}", html, prompt),
                }]
            }
        };

        let request = GenerateContentRequest {
            contents: vec![Content { parts }],
            generation_config: GenerationConfig {
                response_mime_type: "application/json".into(),
                max_output_tokens: 65536,
            },
        };

        let mut last_error = None;
        let mut backoff = INITIAL_BACKOFF_SECS;

        for attempt in 1..=MAX_RETRIES {
            info!("Gemini API attempt {}/{}", attempt, MAX_RETRIES);

            match self.http.post(&url).json(&request).send().await {
                Ok(resp) => {
                    let status = resp.status();
                    if status.is_success() {
                        let body: GenerateContentResponse = resp.json().await?;
                        let text = body
                            .candidates
                            .and_then(|c| c.into_iter().next())
                            .and_then(|c| c.content)
                            .and_then(|c| c.parts)
                            .and_then(|p| p.into_iter().next())
                            .and_then(|p| p.text)
                            .ok_or(LlmError::EmptyResponse)?;

                        info!("Gemini response: {} characters", text.len());
                        return Ok(text);
                    }

                    let error_body = resp.text().await.unwrap_or_default();
                    warn!("Gemini API error ({}): {}", status, error_body);
                    last_error = Some(LlmError::Api {
                        status: status.as_u16(),
                        message: error_body,
                    });
                }
                Err(e) => {
                    warn!("Gemini API request failed: {}", e);
                    last_error = Some(LlmError::Http(e));
                }
            }

            if attempt < MAX_RETRIES {
                info!("Retrying in {}s...", backoff);
                tokio::time::sleep(Duration::from_secs(backoff)).await;
                backoff = (backoff * 2).min(MAX_BACKOFF_SECS);
            }
        }

        Err(last_error.unwrap_or(LlmError::RetriesExhausted {
            attempts: MAX_RETRIES,
        }))
    }

    /// Parse the raw JSON response text into product JSON objects.
    pub fn parse_response(
        &self,
        response_text: &str,
        context: Option<&ExtractionContext>,
    ) -> Result<Vec<serde_json::Value>, LlmError> {
        // Try parsing as array first
        let mut items: Vec<serde_json::Value> = match serde_json::from_str(response_text) {
            Ok(serde_json::Value::Array(arr)) => arr,
            Ok(serde_json::Value::Object(obj)) => vec![serde_json::Value::Object(obj)],
            Ok(_) => return Err(LlmError::Parse("Expected JSON array or object".into())),
            Err(e) => return Err(LlmError::Parse(format!("Invalid JSON: {}", e))),
        };

        // Merge context into each item
        if let Some(ctx) = context {
            for item in &mut items {
                if let Some(obj) = item.as_object_mut() {
                    if let Some(name) = &ctx.product_name {
                        obj.entry("product_name")
                            .or_insert(serde_json::Value::String(name.clone()));
                    }
                    if let Some(mfg) = &ctx.manufacturer {
                        obj.entry("manufacturer")
                            .or_insert(serde_json::Value::String(mfg.clone()));
                    }
                    if let Some(family) = &ctx.product_family {
                        obj.entry("product_family")
                            .or_insert(serde_json::Value::String(family.clone()));
                    }
                    if let Some(url) = &ctx.datasheet_url {
                        obj.entry("datasheet_url")
                            .or_insert(serde_json::Value::String(url.clone()));
                    }
                }
            }
        }

        if items.is_empty() {
            return Err(LlmError::EmptyResponse);
        }

        info!("Parsed {} product(s) from Gemini response", items.len());
        Ok(items)
    }
}

/// Generate a deterministic UUID v5 for a product.
pub fn generate_product_id(
    manufacturer: Option<&str>,
    part_number: Option<&str>,
    product_name: Option<&str>,
) -> Option<uuid::Uuid> {
    let namespace = uuid::Uuid::parse_str("6ba7b810-9dad-11d1-80b4-00c04fd430c8").unwrap();

    let id_string = if let (Some(mfg), Some(pn)) = (manufacturer, part_number) {
        let norm_mfg = normalize_string(mfg);
        let norm_pn = normalize_string(pn);
        if !norm_mfg.is_empty() && !norm_pn.is_empty() {
            format!("{}:{}", norm_mfg, norm_pn)
        } else {
            return None;
        }
    } else if let (Some(mfg), Some(name)) = (manufacturer, product_name) {
        let norm_mfg = normalize_string(mfg);
        let norm_name = normalize_string(name);
        if !norm_mfg.is_empty() && !norm_name.is_empty() {
            format!("{}:{}", norm_mfg, norm_name)
        } else {
            return None;
        }
    } else {
        return None;
    };

    Some(uuid::Uuid::new_v5(&namespace, id_string.as_bytes()))
}

/// Normalize string for ID generation: lowercase, alphanumeric only.
fn normalize_string(s: &str) -> String {
    s.to_lowercase()
        .chars()
        .filter(|c| c.is_alphanumeric())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_product_id_mfg_pn() {
        let id1 = generate_product_id(Some("Delta"), Some("ECMA-C30804"), None);
        let id2 = generate_product_id(Some("Delta"), Some("ECMA-C30804"), None);
        assert!(id1.is_some());
        assert_eq!(id1, id2); // deterministic
    }

    #[test]
    fn test_generate_product_id_mfg_name() {
        let id = generate_product_id(Some("Delta"), None, Some("ECMA Series"));
        assert!(id.is_some());
    }

    #[test]
    fn test_generate_product_id_none() {
        assert!(generate_product_id(None, None, None).is_none());
    }

    #[test]
    fn test_normalize_string() {
        assert_eq!(normalize_string("Nidec Corp."), "nideccorp");
        assert_eq!(normalize_string("Model-A"), "modela");
    }

    #[test]
    fn test_parse_response_array() {
        let client = GeminiClient::new("test".into());
        let json = r#"[{"part_number": "X1"}, {"part_number": "X2"}]"#;
        let items = client.parse_response(json, None).unwrap();
        assert_eq!(items.len(), 2);
    }

    #[test]
    fn test_parse_response_with_context() {
        let client = GeminiClient::new("test".into());
        let json = r#"[{"part_number": "X1"}]"#;
        let ctx = ExtractionContext {
            product_name: Some("Motor A".into()),
            manufacturer: Some("Delta".into()),
            product_family: None,
            datasheet_url: None,
        };
        let items = client.parse_response(json, Some(&ctx)).unwrap();
        assert_eq!(items[0]["manufacturer"], "Delta");
        assert_eq!(items[0]["product_name"], "Motor A");
    }

    #[test]
    fn test_build_prompt_with_context() {
        let client = GeminiClient::new("test".into());
        let ctx = ExtractionContext {
            product_name: Some("UR5e".into()),
            manufacturer: Some("Universal Robots".into()),
            product_family: Some("e-Series".into()),
            datasheet_url: None,
        };
        let prompt = client.build_prompt(Some(&ctx));
        assert!(prompt.contains("UR5e"));
        assert!(prompt.contains("Universal Robots"));
        assert!(prompt.contains("EXTRACTION RULES"));
    }
}
