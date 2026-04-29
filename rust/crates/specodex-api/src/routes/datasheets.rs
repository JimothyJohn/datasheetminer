//! `/api/datasheets` — minimal stub for Phase 3 frontend cutover.
//!
//! The full datasheet CRUD (port of `app/backend/src/routes/datasheets.ts`)
//! is deferred. For now we return an empty list so the AdminPanel's
//! "Datasheets" tab renders without errors. Frontend treats an empty
//! response as "no datasheets found" — which is what dev currently shows
//! anyway since datasheet rows aren't populated by the existing pipeline
//! into `products-{stage}` (they live under separate `DATASHEET#*` keys
//! that this Rust port doesn't expose yet).

use axum::response::Response;

use crate::response::ok_with_count;

pub async fn list() -> Response {
    let empty: Vec<serde_json::Value> = Vec::new();
    ok_with_count(empty, 0)
}
