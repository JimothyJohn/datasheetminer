//! LLM error types.

#[derive(Debug, thiserror::Error)]
pub enum LlmError {
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("API error ({status}): {message}")]
    Api { status: u16, message: String },

    #[error("Parse error: {0}")]
    Parse(String),

    #[error("No valid products in response")]
    EmptyResponse,

    #[error("All retries exhausted after {attempts} attempts")]
    RetriesExhausted { attempts: u32 },

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
}
