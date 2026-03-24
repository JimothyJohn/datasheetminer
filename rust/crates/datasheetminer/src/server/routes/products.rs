//! Product API routes matching the existing Express backend.

use axum::extract::{Path, Query, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::Json;
use dsm_models::common::ProductType;
use dsm_models::Product;
use serde::Deserialize;

use crate::server::response::{ApiResponse, AppError};
use crate::server::state::AppState;

#[derive(Deserialize)]
pub struct ListQuery {
    pub r#type: Option<String>,
    pub limit: Option<i32>,
}

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
        "all" => Err(AppError::BadRequest("Use None for 'all'".into())),
        other => Err(AppError::BadRequest(format!(
            "Invalid product type: {}",
            other
        ))),
    }
}

/// GET /api/products/categories
pub async fn get_categories(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let categories = state.db.get_categories().await?;
    Ok(Json(ApiResponse::ok(categories)))
}

/// GET /api/products/manufacturers
pub async fn get_manufacturers(
    State(state): State<AppState>,
) -> Result<impl IntoResponse, AppError> {
    let manufacturers = state.db.get_unique_manufacturers().await?;
    Ok(Json(ApiResponse::ok(manufacturers)))
}

/// GET /api/products/names
pub async fn get_names(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let names = state.db.get_unique_names().await?;
    Ok(Json(ApiResponse::ok(names)))
}

/// GET /api/products/summary
pub async fn get_summary(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let summary = state.db.get_summary().await?;
    Ok(Json(ApiResponse::ok(summary)))
}

/// GET /api/products
pub async fn list_products(
    State(state): State<AppState>,
    Query(query): Query<ListQuery>,
) -> Result<impl IntoResponse, AppError> {
    let pt = match query.r#type.as_deref() {
        Some("all") | None => None,
        Some(t) => Some(parse_product_type(t)?),
    };
    let products = state.db.list_products(pt, query.limit).await?;
    let count = products.len();
    Ok(Json(ApiResponse::ok_with_count(products, count)))
}

/// GET /api/products/:id
pub async fn get_product(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(query): Query<TypeQuery>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = query
        .r#type
        .as_deref()
        .ok_or_else(|| AppError::BadRequest("type query parameter required".into()))?;
    let pt = parse_product_type(type_str)?;

    match state.db.read_product(&id, pt).await? {
        Some(product) => Ok(Json(ApiResponse::ok(product))),
        None => Err(AppError::NotFound(format!("Product {} not found", id))),
    }
}

/// POST /api/products
pub async fn create_product(
    State(state): State<AppState>,
    Json(body): Json<serde_json::Value>,
) -> Result<impl IntoResponse, AppError> {
    // Handle batch create (array) or single create (object)
    if let Some(arr) = body.as_array() {
        let mut products = Vec::new();
        for item in arr {
            match serde_json::from_value::<Product>(item.clone()) {
                Ok(p) => products.push(p),
                Err(e) => {
                    return Err(AppError::BadRequest(format!("Invalid product: {}", e)));
                }
            }
        }
        let count = state.db.batch_create_products(&products).await?;
        Ok((
            StatusCode::CREATED,
            Json(ApiResponse::ok_with_count(
                serde_json::json!({"created": count}),
                count,
            )),
        )
            .into_response())
    } else {
        let product: Product = serde_json::from_value(body)
            .map_err(|e| AppError::BadRequest(format!("Invalid product: {}", e)))?;
        state.db.create_product(&product).await?;
        Ok((StatusCode::CREATED, Json(ApiResponse::ok(product))).into_response())
    }
}

/// PUT /api/products/:id
pub async fn update_product(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(query): Query<TypeQuery>,
    Json(body): Json<serde_json::Value>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = query
        .r#type
        .as_deref()
        .ok_or_else(|| AppError::BadRequest("type query parameter required".into()))?;
    let pt = parse_product_type(type_str)?;

    let updated = state.db.update_product(&id, pt, body).await?;
    if updated {
        Ok(Json(ApiResponse::<()>::ok_empty()))
    } else {
        Err(AppError::NotFound(format!("Product {} not found", id)))
    }
}

/// DELETE /api/products/:id
pub async fn delete_product(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(query): Query<TypeQuery>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = query
        .r#type
        .as_deref()
        .ok_or_else(|| AppError::BadRequest("type query parameter required".into()))?;
    let pt = parse_product_type(type_str)?;

    state.db.delete_product(&id, pt).await?;
    Ok(Json(ApiResponse::<()>::ok_empty()))
}
