//! DynamoDB operations for datasheetminer.
//!
//! Provides `DynamoClient` with all CRUD, batch, query, and datasheet
//! operations matching the Python `db/dynamo.py` and TypeScript
//! `db/dynamodb.ts` implementations.

pub mod client;
pub mod error;
pub mod serialize;

pub use client::DynamoClient;
pub use error::DbError;
