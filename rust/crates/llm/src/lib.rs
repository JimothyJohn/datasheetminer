//! Gemini API integration for datasheet spec extraction.

pub mod error;
pub mod gemini;

pub use error::LlmError;
pub use gemini::GeminiClient;
