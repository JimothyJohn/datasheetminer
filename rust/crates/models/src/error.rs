//! Model validation errors.

#[derive(Debug, thiserror::Error)]
pub enum ModelError {
    #[error("Invalid ValueUnit format: {0}")]
    InvalidValueUnit(String),

    #[error("Invalid MinMaxUnit format: {0}")]
    InvalidMinMaxUnit(String),

    #[error("Invalid product type: {0}")]
    InvalidProductType(String),

    #[error("Validation error: {0}")]
    Validation(String),
}
