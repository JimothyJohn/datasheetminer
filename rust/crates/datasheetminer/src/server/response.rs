//! Unified API response type matching the existing Express backend.

use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::Json;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct ApiResponse<T: Serialize> {
    pub success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<T>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub count: Option<usize>,
}

impl<T: Serialize> ApiResponse<T> {
    pub fn ok(data: T) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
            count: None,
        }
    }

    pub fn ok_with_count(data: T, count: usize) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
            count: Some(count),
        }
    }
}

impl ApiResponse<()> {
    pub fn error(msg: impl Into<String>) -> Self {
        Self {
            success: false,
            data: None,
            error: Some(msg.into()),
            count: None,
        }
    }

    pub fn ok_empty() -> Self {
        Self {
            success: true,
            data: None,
            error: None,
            count: None,
        }
    }
}

/// Application error type that converts to proper HTTP responses.
#[derive(Debug)]
pub enum AppError {
    NotFound(String),
    BadRequest(String),
    Internal(String),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, msg) = match self {
            AppError::NotFound(m) => (StatusCode::NOT_FOUND, m),
            AppError::BadRequest(m) => (StatusCode::BAD_REQUEST, m),
            AppError::Internal(m) => (StatusCode::INTERNAL_SERVER_ERROR, m),
        };
        (status, Json(ApiResponse::<()>::error(msg))).into_response()
    }
}

impl From<dsm_db::DbError> for AppError {
    fn from(e: dsm_db::DbError) -> Self {
        AppError::Internal(e.to_string())
    }
}
