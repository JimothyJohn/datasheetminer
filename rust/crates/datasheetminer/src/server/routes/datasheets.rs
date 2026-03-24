//! Datasheet API routes.

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use dsm_models::common::ProductType;
use dsm_models::Datasheet;
use serde::Deserialize;

use crate::server::response::{ApiResponse, AppError};
use crate::server::state::AppState;

#[derive(Deserialize)]
pub struct TypeQuery {
    pub r#type: Option<String>,
}

fn parse_product_type(s: &str) -> Result<ProductType, AppError> {
    match s {
        "motor" => Ok(ProductType::Motor),
        "drive" => Ok(ProductType::Drive),
        "gearhead" => Ok(ProductType::Gearhead),
        "robot_arm" => Ok(ProductType::RobotArm),
        "datasheet" => Ok(ProductType::Datasheet),
        other => Err(AppError::BadRequest(format!("Invalid type: {}", other))),
    }
}

/// GET /api/datasheets
pub async fn list_datasheets(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let datasheets = state.db.list_datasheets().await?;
    let count = datasheets.len();
    Ok(Json(ApiResponse::ok_with_count(datasheets, count)))
}

/// POST /api/datasheets
pub async fn create_datasheet(
    State(state): State<AppState>,
    Json(body): Json<serde_json::Value>,
) -> Result<impl IntoResponse, AppError> {
    let datasheet: Datasheet = serde_json::from_value(body)
        .map_err(|e| AppError::BadRequest(format!("Invalid datasheet: {}", e)))?;
    state.db.create_datasheet(&datasheet).await?;
    Ok((StatusCode::CREATED, Json(ApiResponse::ok(datasheet))).into_response())
}

/// PUT /api/datasheets/:id
pub async fn update_datasheet(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = body["product_type"]
        .as_str()
        .ok_or_else(|| AppError::BadRequest("product_type required in body".into()))?;
    let pt = parse_product_type(type_str)?;

    let updated = state.db.update_datasheet(&id, pt, body).await?;
    if updated {
        Ok(Json(ApiResponse::<()>::ok_empty()))
    } else {
        Err(AppError::NotFound(format!("Datasheet {} not found", id)))
    }
}

/// DELETE /api/datasheets/:id
pub async fn delete_datasheet(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(query): Query<TypeQuery>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = query
        .r#type
        .as_deref()
        .ok_or_else(|| AppError::BadRequest("type query parameter required".into()))?;
    let pt = parse_product_type(type_str)?;

    state.db.delete_datasheet(&id, pt).await?;
    Ok(Json(ApiResponse::<()>::ok_empty()))
}
