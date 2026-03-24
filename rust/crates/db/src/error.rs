//! Database error types.

use aws_sdk_dynamodb::operation::{
    batch_write_item::BatchWriteItemError, delete_item::DeleteItemError, get_item::GetItemError,
    put_item::PutItemError, query::QueryError, scan::ScanError,
};

#[derive(Debug, thiserror::Error)]
pub enum DbError {
    #[error("DynamoDB PutItem error: {0}")]
    PutItem(#[from] Box<aws_sdk_dynamodb::error::SdkError<PutItemError>>),

    #[error("DynamoDB GetItem error: {0}")]
    GetItem(#[from] Box<aws_sdk_dynamodb::error::SdkError<GetItemError>>),

    #[error("DynamoDB DeleteItem error: {0}")]
    DeleteItem(#[from] Box<aws_sdk_dynamodb::error::SdkError<DeleteItemError>>),

    #[error("DynamoDB Query error: {0}")]
    Query(#[from] Box<aws_sdk_dynamodb::error::SdkError<QueryError>>),

    #[error("DynamoDB Scan error: {0}")]
    Scan(#[from] Box<aws_sdk_dynamodb::error::SdkError<ScanError>>),

    #[error("DynamoDB BatchWrite error: {0}")]
    BatchWrite(#[from] Box<aws_sdk_dynamodb::error::SdkError<BatchWriteItemError>>),

    #[error("Serialization error: {0}")]
    Serialization(String),

    #[error("Item not found: PK={pk}, SK={sk}")]
    NotFound { pk: String, sk: String },
}
