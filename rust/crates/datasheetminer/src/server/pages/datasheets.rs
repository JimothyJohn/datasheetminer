//! Datasheets page handlers.

use askama::Template;
use axum::extract::{Form, Path, Query, State};
use axum::response::{Html, IntoResponse};
use dsm_models::common::ProductType;
use dsm_models::Datasheet;
use serde::Deserialize;
use uuid::Uuid;

use crate::server::response::AppError;
use crate::server::state::AppState;

pub struct DatasheetRow {
    pub id: String,
    pub product_name: String,
    pub product_type: String,
    pub product_family: String,
    pub manufacturer: String,
    pub url: String,
}

#[derive(Template)]
#[template(path = "datasheets.html")]
struct DatasheetsPage {
    active: &'static str,
    datasheets: Vec<DatasheetRow>,
}

#[derive(Deserialize)]
pub struct CreateForm {
    pub product_name: String,
    pub product_type: String,
    pub url: String,
    pub manufacturer: Option<String>,
    pub product_family: Option<String>,
    #[allow(dead_code)]
    pub pages: Option<String>,
}

#[derive(Deserialize)]
pub struct DeleteQuery {
    pub r#type: Option<String>,
}

fn to_rows(datasheets: Vec<Datasheet>) -> Vec<DatasheetRow> {
    datasheets
        .into_iter()
        .map(|ds| DatasheetRow {
            id: ds.datasheet_id.to_string(),
            product_name: ds.product_name,
            product_type: ds.product_type.as_str().to_string(),
            product_family: ds.product_family.unwrap_or_default(),
            manufacturer: ds.manufacturer.unwrap_or_default(),
            url: ds.url,
        })
        .collect()
}

/// GET /datasheets
pub async fn index(State(state): State<AppState>) -> Result<impl IntoResponse, AppError> {
    let datasheets = state.db.list_datasheets().await?;
    let tmpl = DatasheetsPage {
        active: "datasheets",
        datasheets: to_rows(datasheets),
    };
    Ok(Html(
        tmpl.render()
            .map_err(|e| AppError::Internal(e.to_string()))?,
    ))
}

/// POST /datasheets — create via form
pub async fn create(
    State(state): State<AppState>,
    Form(form): Form<CreateForm>,
) -> Result<impl IntoResponse, AppError> {
    let pt = match form.product_type.as_str() {
        "motor" => ProductType::Motor,
        "drive" => ProductType::Drive,
        "gearhead" => ProductType::Gearhead,
        "robot_arm" => ProductType::RobotArm,
        _ => {
            return Ok(Html(
                r#"<div class="result-msg error">Invalid product type</div>"#.to_string(),
            ))
        }
    };

    let ds = Datasheet {
        datasheet_id: Uuid::new_v4(),
        url: form.url,
        pages: None,
        product_type: pt,
        product_name: form.product_name,
        product_family: form.product_family,
        manufacturer: form.manufacturer,
        category: None,
        release_year: None,
        warranty: None,
    };

    state.db.create_datasheet(&ds).await?;

    // Return updated rows
    let datasheets = state.db.list_datasheets().await?;
    let _rows = to_rows(datasheets);
    Ok(Html(
        r#"<div class="result-msg success">Datasheet added</div>"#.to_string(),
    ))
}

/// POST /datasheets/:id/delete
pub async fn delete(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(query): Query<DeleteQuery>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = query.r#type.as_deref().unwrap_or("motor");
    let pt = match type_str {
        "motor" => ProductType::Motor,
        "drive" => ProductType::Drive,
        "gearhead" => ProductType::Gearhead,
        "robot_arm" => ProductType::RobotArm,
        "datasheet" => ProductType::Datasheet,
        _ => ProductType::Motor,
    };

    state.db.delete_datasheet(&id, pt).await?;
    // Return empty string to remove the row via hx-swap="outerHTML"
    Ok(Html(String::new()))
}
