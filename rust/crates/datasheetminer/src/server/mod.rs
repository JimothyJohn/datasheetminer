//! Axum web server: REST API + server-rendered HTML frontend with HTMX.

pub mod pages;
pub mod response;
pub mod routes;
pub mod state;

use std::sync::Arc;

use axum::http::{header, StatusCode};
use axum::response::IntoResponse;
use axum::routing::{get, post, put};
use axum::Router;
use dsm_db::DynamoClient;
use tower_http::cors::{Any, CorsLayer};
use tracing::info;

use state::AppState;

/// Embedded static assets — served from the compiled binary, zero external deps.
const STYLE_CSS: &str = include_str!("../../templates/style.css");
const HTMX_JS: &str = include_str!("../../templates/htmx.min.js");

async fn serve_css() -> impl IntoResponse {
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/css")],
        STYLE_CSS,
    )
}

async fn serve_htmx() -> impl IntoResponse {
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "application/javascript")],
        HTMX_JS,
    )
}

/// Build the full Axum router.
pub fn build_router(db: DynamoClient) -> Router {
    let state = AppState { db: Arc::new(db) };

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        // Static assets (embedded in binary)
        .route("/static/style.css", get(serve_css))
        .route("/static/htmx.min.js", get(serve_htmx))
        // Health
        .route("/health", get(routes::health::health_check))
        // HTML pages (server-rendered + HTMX)
        .route("/", get(pages::products::index))
        .route("/products", get(pages::products::index))
        .route("/products/{id}", get(pages::products::detail))
        .route(
            "/datasheets",
            get(pages::datasheets::index).post(pages::datasheets::create),
        )
        .route("/datasheets/{id}/delete", post(pages::datasheets::delete))
        .route("/management", get(pages::management::index))
        .route(
            "/management/delete",
            post(pages::management::delete_by_type),
        )
        .route("/management/dedup", post(pages::management::dedup))
        .route(
            "/management/delete-all",
            post(pages::management::delete_all),
        )
        // JSON API (unchanged)
        .route(
            "/api/products/categories",
            get(routes::products::get_categories),
        )
        .route(
            "/api/products/manufacturers",
            get(routes::products::get_manufacturers),
        )
        .route("/api/products/names", get(routes::products::get_names))
        .route("/api/products/summary", get(routes::products::get_summary))
        .route(
            "/api/products",
            get(routes::products::list_products).post(routes::products::create_product),
        )
        .route(
            "/api/products/{id}",
            get(routes::products::get_product)
                .put(routes::products::update_product)
                .delete(routes::products::delete_product),
        )
        .route(
            "/api/datasheets",
            get(routes::datasheets::list_datasheets).post(routes::datasheets::create_datasheet),
        )
        .route(
            "/api/datasheets/{id}",
            put(routes::datasheets::update_datasheet).delete(routes::datasheets::delete_datasheet),
        )
        .with_state(state)
        .layer(cors)
}

/// Start the server on the given port.
pub async fn start(
    port: u16,
    table: &str,
    _static_dir: Option<std::path::PathBuf>,
) -> anyhow::Result<()> {
    let db = DynamoClient::from_env(table).await;
    let router = build_router(db);

    let addr = format!("0.0.0.0:{}", port);
    info!("Server listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, router).await?;

    Ok(())
}
