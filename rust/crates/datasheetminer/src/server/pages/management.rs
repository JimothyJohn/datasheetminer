//! Management page handlers.

use askama::Template;
use axum::extract::{Form, State};
use axum::response::{Html, IntoResponse};
use dsm_models::common::ProductType;
use serde::Deserialize;

use crate::server::response::AppError;
use crate::server::state::AppState;

#[derive(Template)]
#[template(path = "management.html")]
struct ManagementPage {
    active: &'static str,
}

#[derive(Deserialize)]
pub struct DeleteForm {
    pub product_type: String,
    pub action: String,
}

#[derive(Deserialize)]
pub struct DedupForm {
    pub action: String,
}

/// GET /management
pub async fn index() -> Result<impl IntoResponse, AppError> {
    let tmpl = ManagementPage {
        active: "management",
    };
    Ok(Html(
        tmpl.render()
            .map_err(|e| AppError::Internal(e.to_string()))?,
    ))
}

/// POST /management/delete
pub async fn delete_by_type(
    State(state): State<AppState>,
    Form(form): Form<DeleteForm>,
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

    let dry_run = form.action == "dry_run";
    let count = state.db.delete_by_product_type(pt, dry_run).await?;

    let msg = if dry_run {
        format!(
            "Dry run: would delete {} {} products",
            count, form.product_type
        )
    } else {
        format!("Deleted {} {} products", count, form.product_type)
    };

    Ok(Html(format!(
        r#"<div class="result-msg success">{}</div>"#,
        msg
    )))
}

/// POST /management/dedup
pub async fn dedup(
    State(state): State<AppState>,
    Form(form): Form<DedupForm>,
) -> Result<impl IntoResponse, AppError> {
    let dry_run = form.action == "dry_run";
    let products = state.db.list_products(None, None).await?;

    // Find duplicates by (part_number, product_name, manufacturer)
    let mut groups: std::collections::HashMap<String, Vec<(String, String)>> =
        std::collections::HashMap::new();
    for product in &products {
        let base = product.base();
        let key = format!(
            "{}|{}|{}",
            base.part_number.as_deref().unwrap_or(""),
            base.product_name,
            base.manufacturer.as_deref().unwrap_or(""),
        );
        groups
            .entry(key)
            .or_default()
            .push((product.pk(), product.sk()));
    }

    let mut keys_to_delete = Vec::new();
    let mut dup_count = 0;
    for items in groups.values() {
        if items.len() > 1 {
            dup_count += items.len() - 1;
            for item in &items[1..] {
                keys_to_delete.push(item.clone());
            }
        }
    }

    if dry_run {
        return Ok(Html(format!(
            r#"<div class="result-msg success">Dry run: found {} duplicates across {} total products</div>"#,
            dup_count,
            products.len()
        )));
    }

    if keys_to_delete.is_empty() {
        return Ok(Html(
            r#"<div class="result-msg success">No duplicates found</div>"#.to_string(),
        ));
    }

    let deleted = state.db.batch_delete(&keys_to_delete).await?;
    Ok(Html(format!(
        r#"<div class="result-msg success">Deleted {} duplicate products</div>"#,
        deleted
    )))
}

/// POST /management/delete-all
pub async fn delete_all(
    State(state): State<AppState>,
    Form(form): Form<DedupForm>,
) -> Result<impl IntoResponse, AppError> {
    let dry_run = form.action == "dry_run";
    let count = state.db.delete_all(dry_run).await?;

    let msg = if dry_run {
        format!("Dry run: would delete {} items", count)
    } else {
        format!("Deleted {} items", count)
    };

    Ok(Html(format!(
        r#"<div class="result-msg success">{}</div>"#,
        msg
    )))
}
