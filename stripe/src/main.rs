mod checkout;
mod config;
mod db;
mod models;
mod usage;
mod webhook;

use lambda_http::{run, service_fn, Body, Error, Request, Response};
use tracing::info;

use crate::config::Config;
use crate::db::UsersDb;
use crate::models::{CheckoutRequest, ErrorResponse, StatusResponse, UsageRequest};

struct AppState {
    config: Config,
    db: UsersDb,
    stripe_client: stripe::Client,
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .json()
        .without_time()
        .init();

    let config = Config::from_env();

    // Hard guard: refuse to start with live keys
    if !config.is_test_mode() {
        panic!("REFUSING TO START: STRIPE_SECRET_KEY is not a test key. Set sk_test_... to proceed.");
    }

    let stripe_client = stripe::Client::new(&config.stripe_secret_key);

    let aws_config = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let dynamo_client = aws_sdk_dynamodb::Client::new(&aws_config);
    let db = UsersDb::new(dynamo_client, config.users_table_name.clone());

    let state = &*Box::leak(Box::new(AppState {
        config,
        db,
        stripe_client,
    }));

    info!("Starting payments Lambda (TEST MODE)");

    run(service_fn(|event: Request| async move {
        router(state, event).await
    }))
    .await
}

async fn router(state: &AppState, req: Request) -> Result<Response<Body>, Error> {
    let path = req.uri().path();
    let method = req.method().as_str();

    info!(method, path, "Incoming request");

    match (method, path) {
        ("POST", "/checkout") => handle_checkout(state, req).await,
        ("POST", "/webhook") => handle_webhook(state, req).await,
        ("POST", "/usage") => handle_usage(state, req).await,
        ("GET", path) if path.starts_with("/status/") => handle_status(state, req).await,
        ("GET", "/health") => ok_json(&serde_json::json!({"status": "ok", "mode": "test"})),
        _ => {
            let body = serde_json::to_string(&ErrorResponse {
                error: "Not found".into(),
            })?;
            Ok(Response::builder()
                .status(404)
                .header("content-type", "application/json")
                .body(Body::from(body))?)
        }
    }
}

async fn handle_checkout(state: &AppState, req: Request) -> Result<Response<Body>, Error> {
    let body = std::str::from_utf8(req.body().as_ref()).unwrap_or("");
    let checkout_req: CheckoutRequest = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err_json(400, &format!("Invalid request: {e}")),
    };

    match checkout::create_checkout_session(
        &state.config,
        &state.db,
        &state.stripe_client,
        checkout_req,
    )
    .await
    {
        Ok(resp) => ok_json(&resp),
        Err(e) => err_json(400, &e),
    }
}

async fn handle_webhook(state: &AppState, req: Request) -> Result<Response<Body>, Error> {
    let signature = req
        .headers()
        .get("stripe-signature")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let body = std::str::from_utf8(req.body().as_ref()).unwrap_or("");

    match webhook::handle_webhook(&state.config, &state.db, signature, body).await {
        Ok(()) => ok_json(&serde_json::json!({"received": true})),
        Err(e) => err_json(400, &e),
    }
}

async fn handle_usage(state: &AppState, req: Request) -> Result<Response<Body>, Error> {
    let body = std::str::from_utf8(req.body().as_ref()).unwrap_or("");
    let usage_req: UsageRequest = match serde_json::from_str(body) {
        Ok(r) => r,
        Err(e) => return err_json(400, &format!("Invalid request: {e}")),
    };

    match usage::report_usage(&state.db, &state.stripe_client, usage_req).await {
        Ok(resp) => ok_json(&resp),
        Err(e) => err_json(400, &e),
    }
}

async fn handle_status(state: &AppState, req: Request) -> Result<Response<Body>, Error> {
    let user_id = req
        .uri()
        .path()
        .strip_prefix("/status/")
        .unwrap_or("");

    if user_id.is_empty() {
        return err_json(400, "Missing user_id");
    }

    match state.db.get_user(user_id).await {
        Ok(Some(user)) => ok_json(&StatusResponse {
            user_id: user.user_id,
            subscription_status: user.subscription_status,
            stripe_customer_id: Some(user.stripe_customer_id),
        }),
        Ok(None) => ok_json(&StatusResponse {
            user_id: user_id.to_string(),
            subscription_status: models::SubscriptionStatus::None,
            stripe_customer_id: None,
        }),
        Err(e) => err_json(500, &e),
    }
}

fn ok_json<T: serde::Serialize>(data: &T) -> Result<Response<Body>, Error> {
    let body = serde_json::to_string(data)?;
    Ok(Response::builder()
        .status(200)
        .header("content-type", "application/json")
        .body(Body::from(body))?)
}

fn err_json(status: u16, msg: &str) -> Result<Response<Body>, Error> {
    let body = serde_json::to_string(&ErrorResponse {
        error: msg.to_string(),
    })?;
    Ok(Response::builder()
        .status(status)
        .header("content-type", "application/json")
        .body(Body::from(body))?)
}
