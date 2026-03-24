//! Products page handlers.

use askama::Template;
use axum::extract::{Path, Query, State};
use axum::http::HeaderMap;
use axum::response::{Html, IntoResponse};
use serde::Deserialize;

use crate::server::pages::filters::{format_label, format_spec};
use crate::server::response::AppError;
use crate::server::state::AppState;

use dsm_models::common::ProductType;

// --- Data types for templates ---

pub struct Category {
    pub type_name: String,
    pub display_name: String,
    pub count: usize,
}

pub struct Column {
    pub field: String,
    pub label: String,
}

pub struct ProductRow {
    pub id: String,
    pub product_type: String,
    pub fields: serde_json::Map<String, serde_json::Value>,
}

impl ProductRow {
    pub fn get_field(&self, field: &str) -> String {
        match self.fields.get(field) {
            Some(v) => format_spec(v).unwrap_or_else(|_| "—".into()),
            None => "—".into(),
        }
    }
}

pub struct DetailItem {
    pub label: String,
    pub value: String,
}

// --- Query params ---

#[derive(Deserialize)]
pub struct ProductsQuery {
    pub r#type: Option<String>,
    pub sort: Option<String>,
    pub dir: Option<String>,
    pub page: Option<usize>,
    pub page_size: Option<usize>,
}

#[derive(Deserialize)]
pub struct DetailQuery {
    pub r#type: Option<String>,
}

// --- Templates ---

#[derive(Template)]
#[template(path = "products.html")]
struct ProductsPage {
    active: &'static str,
    categories: Vec<Category>,
    products: Vec<ProductRow>,
    columns: Vec<Column>,
    product_type: String,
    sort_col: String,
    sort_dir: String,
    page: usize,
    page_size: usize,
    total: usize,
    total_all: usize,
    total_pages: usize,
    start: usize,
    end: usize,
    page_range: Vec<usize>,
}

#[derive(Template)]
#[template(path = "product_table.html")]
struct ProductTable {
    products: Vec<ProductRow>,
    columns: Vec<Column>,
    product_type: String,
    sort_col: String,
    sort_dir: String,
    page: usize,
    page_size: usize,
    total: usize,
    total_pages: usize,
    start: usize,
    end: usize,
    page_range: Vec<usize>,
}

#[derive(Template)]
#[template(path = "product_detail.html")]
struct ProductDetail {
    product_name: String,
    manufacturer: Option<String>,
    part_number: Option<String>,
    datasheet_url: Option<String>,
    specs: Vec<DetailItem>,
}

// --- Default columns per product type ---

fn columns_for_type(product_type: &str) -> Vec<Column> {
    let mut cols = vec![
        Column {
            field: "part_number".into(),
            label: "Part Number".into(),
        },
        Column {
            field: "manufacturer".into(),
            label: "Manufacturer".into(),
        },
    ];

    let type_cols: Vec<(&str, &str)> = match product_type {
        "motor" => vec![
            ("rated_power", "Power"),
            ("rated_voltage", "Voltage"),
            ("rated_current", "Current"),
            ("rated_speed", "Speed"),
            ("rated_torque", "Torque"),
            ("peak_torque", "Peak Torque"),
        ],
        "drive" => vec![
            ("output_power", "Power"),
            ("input_voltage", "Input V"),
            ("rated_current", "Current"),
            ("peak_current", "Peak Current"),
        ],
        "gearhead" => vec![
            ("gear_ratio", "Ratio"),
            ("max_continuous_torque", "Cont. Torque"),
            ("max_peak_torque", "Peak Torque"),
            ("backlash", "Backlash"),
            ("efficiency", "Efficiency"),
        ],
        "robot_arm" => vec![
            ("payload", "Payload"),
            ("reach", "Reach"),
            ("degrees_of_freedom", "DOF"),
            ("pose_repeatability", "Repeatability"),
            ("max_tcp_speed", "TCP Speed"),
        ],
        _ => vec![("product_family", "Family"), ("weight", "Weight")],
    };

    for (field, label) in type_cols {
        cols.push(Column {
            field: field.into(),
            label: label.into(),
        });
    }
    cols
}

const META_FIELDS: &[&str] = &[
    "product_id",
    "product_type",
    "product_name",
    "PK",
    "SK",
    "datasheet_url",
    "pages",
    "product_family",
    "part_number",
    "manufacturer",
    "dimensions",
    "release_year",
];

// --- Handlers ---

/// GET / or GET /products — product list page
pub async fn index(
    headers: HeaderMap,
    State(state): State<AppState>,
    Query(query): Query<ProductsQuery>,
) -> Result<impl IntoResponse, AppError> {
    let product_type = query.r#type.as_deref().unwrap_or("all");
    let sort_col = query.sort.as_deref().unwrap_or("product_name");
    let sort_dir = query.dir.as_deref().unwrap_or("asc");
    let page = query.page.unwrap_or(1).max(1);
    let page_size = query.page_size.unwrap_or(25);

    // Fetch products
    let pt = match product_type {
        "all" => None,
        "motor" => Some(ProductType::Motor),
        "drive" => Some(ProductType::Drive),
        "gearhead" => Some(ProductType::Gearhead),
        "robot_arm" => Some(ProductType::RobotArm),
        _ => None,
    };
    let all_products = state.db.list_products(pt, None).await?;

    // Convert to JSON for flexible field access
    let mut json_products: Vec<serde_json::Value> = all_products
        .iter()
        .filter_map(|p| serde_json::to_value(p).ok())
        .collect();

    // Sort
    json_products.sort_by(|a, b| {
        let va = field_sort_key(a, sort_col);
        let vb = field_sort_key(b, sort_col);
        let cmp = va.partial_cmp(&vb).unwrap_or(std::cmp::Ordering::Equal);
        if sort_dir == "desc" {
            cmp.reverse()
        } else {
            cmp
        }
    });

    let total = json_products.len();
    let total_pages = if total == 0 {
        1
    } else {
        total.div_ceil(page_size)
    };
    let page = page.min(total_pages);
    let start_idx = (page - 1) * page_size;
    let end_idx = (start_idx + page_size).min(total);

    let columns = columns_for_type(if product_type == "all" {
        ""
    } else {
        product_type
    });

    let products: Vec<ProductRow> = json_products[start_idx..end_idx]
        .iter()
        .map(|v| {
            let obj = v.as_object().cloned().unwrap_or_default();
            ProductRow {
                id: obj
                    .get("product_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                product_type: obj
                    .get("product_type")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                fields: obj,
            }
        })
        .collect();

    // Pagination range
    let page_range = compute_page_range(page, total_pages);

    // HTMX partial: return just the table
    if headers.contains_key("hx-request") {
        let tmpl = ProductTable {
            products,
            columns,
            product_type: product_type.into(),
            sort_col: sort_col.into(),
            sort_dir: sort_dir.into(),
            page,
            page_size,
            total,
            total_pages,
            start: start_idx + 1,
            end: end_idx,
            page_range,
        };
        return Ok(Html(
            tmpl.render()
                .map_err(|e| AppError::Internal(e.to_string()))?,
        )
        .into_response());
    }

    // Full page
    let categories_data = state.db.get_categories().await?;
    let total_all: usize = categories_data
        .iter()
        .filter_map(|c| c["count"].as_u64())
        .sum::<u64>() as usize;

    let categories: Vec<Category> = categories_data
        .iter()
        .map(|c| Category {
            type_name: c["type"].as_str().unwrap_or("").to_string(),
            display_name: c["display_name"].as_str().unwrap_or("").to_string(),
            count: c["count"].as_u64().unwrap_or(0) as usize,
        })
        .collect();

    let tmpl = ProductsPage {
        active: "products",
        categories,
        products,
        columns,
        product_type: product_type.into(),
        sort_col: sort_col.into(),
        sort_dir: sort_dir.into(),
        page,
        page_size,
        total,
        total_all,
        total_pages,
        start: start_idx + 1,
        end: end_idx,
        page_range,
    };

    Ok(Html(
        tmpl.render()
            .map_err(|e| AppError::Internal(e.to_string()))?,
    )
    .into_response())
}

/// GET /products/:id — product detail (HTMX partial)
pub async fn detail(
    State(state): State<AppState>,
    Path(id): Path<String>,
    Query(query): Query<DetailQuery>,
) -> Result<impl IntoResponse, AppError> {
    let type_str = query.r#type.as_deref().unwrap_or("motor");
    let pt = match type_str {
        "motor" => ProductType::Motor,
        "drive" => ProductType::Drive,
        "gearhead" => ProductType::Gearhead,
        "robot_arm" => ProductType::RobotArm,
        _ => ProductType::Motor,
    };

    let product = state
        .db
        .read_product(&id, pt)
        .await?
        .ok_or_else(|| AppError::NotFound(format!("Product {} not found", id)))?;

    let json = serde_json::to_value(&product).unwrap_or_default();
    let obj = json.as_object().cloned().unwrap_or_default();

    let product_name = obj
        .get("product_name")
        .and_then(|v| v.as_str())
        .unwrap_or("Unknown")
        .to_string();
    let manufacturer = obj
        .get("manufacturer")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let part_number = obj
        .get("part_number")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let datasheet_url = obj
        .get("datasheet_url")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let specs: Vec<DetailItem> = obj
        .iter()
        .filter(|(k, v)| !META_FIELDS.contains(&k.as_str()) && !v.is_null())
        .map(|(k, v)| DetailItem {
            label: format_label(k).unwrap_or_else(|_| k.clone()),
            value: format_spec(v).unwrap_or_else(|_| "—".into()),
        })
        .collect();

    let tmpl = ProductDetail {
        product_name,
        manufacturer,
        part_number,
        datasheet_url,
        specs,
    };

    Ok(Html(
        tmpl.render()
            .map_err(|e| AppError::Internal(e.to_string()))?,
    ))
}

// --- Helpers ---

fn field_sort_key(v: &serde_json::Value, field: &str) -> SortKey {
    let val = v.get(field);
    match val {
        None | Some(serde_json::Value::Null) => SortKey::Null,
        Some(serde_json::Value::Number(n)) => SortKey::Num(n.as_f64().unwrap_or(0.0)),
        Some(serde_json::Value::String(s)) => {
            // Try to extract numeric part from "value;unit"
            if let Some((num_str, _)) = s.split_once(';') {
                if let Ok(n) = num_str.parse::<f64>() {
                    return SortKey::Num(n);
                }
            }
            SortKey::Str(s.to_lowercase())
        }
        Some(serde_json::Value::Bool(b)) => SortKey::Num(if *b { 1.0 } else { 0.0 }),
        _ => SortKey::Str(val.map(|v| v.to_string()).unwrap_or_default()),
    }
}

#[derive(PartialEq, PartialOrd)]
enum SortKey {
    Null,
    Num(f64),
    Str(String),
}

fn compute_page_range(current: usize, total: usize) -> Vec<usize> {
    let start = current.saturating_sub(2).max(1);
    let end = (start + 4).min(total);
    let start = if end >= 5 {
        end.saturating_sub(4)
    } else {
        start
    };
    (start..=end).collect()
}
