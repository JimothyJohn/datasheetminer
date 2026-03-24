//! DynamoDB client with CRUD operations for datasheetminer models.

use std::collections::HashMap;

use aws_sdk_dynamodb::types::AttributeValue;
use aws_sdk_dynamodb::Client;
use tracing::{error, info, warn};

use dsm_models::common::ProductType;
use dsm_models::product::Product;
use dsm_models::Datasheet;

use crate::error::DbError;
use crate::serialize::{from_dynamo_item, to_dynamo_item};

/// Valid product types for queries (matches TypeScript VALID_PRODUCT_TYPES).
const VALID_PRODUCT_TYPES: &[ProductType] = &[
    ProductType::Motor,
    ProductType::Drive,
    ProductType::Gearhead,
    ProductType::RobotArm,
];

pub struct DynamoClient {
    client: Client,
    table_name: String,
}

impl DynamoClient {
    pub fn new(client: Client, table_name: String) -> Self {
        Self { client, table_name }
    }

    /// Build from AWS SDK config with default credentials.
    pub async fn from_env(table_name: &str) -> Self {
        let config = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
        let client = Client::new(&config);
        Self::new(client, table_name.to_string())
    }

    // -----------------------------------------------------------------------
    // Product CRUD
    // -----------------------------------------------------------------------

    /// Create a product in DynamoDB.
    pub async fn create_product(&self, product: &Product) -> Result<(), DbError> {
        let mut json =
            serde_json::to_value(product).map_err(|e| DbError::Serialization(e.to_string()))?;

        // Inject PK/SK
        let obj = json.as_object_mut().unwrap();
        obj.insert("PK".into(), serde_json::Value::String(product.pk()));
        obj.insert("SK".into(), serde_json::Value::String(product.sk()));

        let item = to_dynamo_item(&json)?;
        self.client
            .put_item()
            .table_name(&self.table_name)
            .set_item(Some(item))
            .send()
            .await
            .map_err(Box::new)?;

        info!("Created product: {}", product.sk());
        Ok(())
    }

    /// Read a product by ID and type.
    pub async fn read_product(
        &self,
        product_id: &str,
        product_type: ProductType,
    ) -> Result<Option<Product>, DbError> {
        let pk = format!("PRODUCT#{}", product_type.as_str().to_uppercase());
        let sk = format!("PRODUCT#{}", product_id);

        let result = self
            .client
            .get_item()
            .table_name(&self.table_name)
            .key("PK", AttributeValue::S(pk.clone()))
            .key("SK", AttributeValue::S(sk.clone()))
            .send()
            .await
            .map_err(Box::new)?;

        let Some(item) = result.item else {
            return Ok(None);
        };

        let json = from_dynamo_item(&item);
        match serde_json::from_value::<Product>(json) {
            Ok(product) => Ok(Some(product)),
            Err(e) => {
                warn!("Failed to deserialize product {}/{}: {}", pk, sk, e);
                Ok(None)
            }
        }
    }

    /// Delete a product by ID and type.
    pub async fn delete_product(
        &self,
        product_id: &str,
        product_type: ProductType,
    ) -> Result<(), DbError> {
        let pk = format!("PRODUCT#{}", product_type.as_str().to_uppercase());
        let sk = format!("PRODUCT#{}", product_id);

        self.client
            .delete_item()
            .table_name(&self.table_name)
            .key("PK", AttributeValue::S(pk))
            .key("SK", AttributeValue::S(sk))
            .send()
            .await
            .map_err(Box::new)?;

        Ok(())
    }

    /// Update a product (read-modify-write via PutItem).
    pub async fn update_product(
        &self,
        product_id: &str,
        product_type: ProductType,
        updates: serde_json::Value,
    ) -> Result<bool, DbError> {
        let pk = format!("PRODUCT#{}", product_type.as_str().to_uppercase());
        let sk = format!("PRODUCT#{}", product_id);

        // Fetch existing
        let result = self
            .client
            .get_item()
            .table_name(&self.table_name)
            .key("PK", AttributeValue::S(pk.clone()))
            .key("SK", AttributeValue::S(sk.clone()))
            .send()
            .await
            .map_err(Box::new)?;

        let Some(existing_item) = result.item else {
            return Ok(false);
        };

        let mut json = from_dynamo_item(&existing_item);
        // Merge updates
        if let (Some(base), Some(upd)) = (json.as_object_mut(), updates.as_object()) {
            for (k, v) in upd {
                base.insert(k.clone(), v.clone());
            }
            // Ensure PK/SK don't change
            base.insert("PK".into(), serde_json::Value::String(pk));
            base.insert("SK".into(), serde_json::Value::String(sk));
        }

        let item = to_dynamo_item(&json)?;
        self.client
            .put_item()
            .table_name(&self.table_name)
            .set_item(Some(item))
            .send()
            .await
            .map_err(Box::new)?;

        Ok(true)
    }

    // -----------------------------------------------------------------------
    // Product queries
    // -----------------------------------------------------------------------

    /// List products of a specific type. If `product_type` is None, lists all.
    pub async fn list_products(
        &self,
        product_type: Option<ProductType>,
        limit: Option<i32>,
    ) -> Result<Vec<Product>, DbError> {
        match product_type {
            Some(pt) => self.query_products_by_type(pt, limit).await,
            None => {
                let mut all = Vec::new();
                for &pt in VALID_PRODUCT_TYPES {
                    let products = self.query_products_by_type(pt, limit).await?;
                    all.extend(products);
                }
                Ok(all)
            }
        }
    }

    /// Query products by partition key (product type).
    async fn query_products_by_type(
        &self,
        product_type: ProductType,
        limit: Option<i32>,
    ) -> Result<Vec<Product>, DbError> {
        let pk = format!("PRODUCT#{}", product_type.as_str().to_uppercase());
        let mut products = Vec::new();
        let mut exclusive_start_key: Option<HashMap<String, AttributeValue>> = None;

        loop {
            let mut query = self
                .client
                .query()
                .table_name(&self.table_name)
                .key_condition_expression("PK = :pk")
                .expression_attribute_values(":pk", AttributeValue::S(pk.clone()));

            if let Some(l) = limit {
                query = query.limit(l);
            }
            if let Some(ref key) = exclusive_start_key {
                query = query.set_exclusive_start_key(Some(key.clone()));
            }

            let result = query.send().await.map_err(Box::new)?;

            if let Some(items) = result.items {
                for item in &items {
                    let json = from_dynamo_item(item);
                    match serde_json::from_value::<Product>(json) {
                        Ok(product) => products.push(product),
                        Err(e) => warn!("Skipping undeserializable item: {}", e),
                    }
                }
            }

            // Stop paginating if limit was set or no more pages
            if limit.is_some() || result.last_evaluated_key.is_none() {
                break;
            }
            exclusive_start_key = result.last_evaluated_key;
        }

        Ok(products)
    }

    /// Check if a product exists by type, manufacturer, and name.
    pub async fn product_exists(
        &self,
        product_type: ProductType,
        manufacturer: &str,
        product_name: &str,
    ) -> Result<bool, DbError> {
        let pk = format!("PRODUCT#{}", product_type.as_str().to_uppercase());

        let result = self
            .client
            .query()
            .table_name(&self.table_name)
            .key_condition_expression("PK = :pk")
            .filter_expression("manufacturer = :mfg AND product_name = :name")
            .expression_attribute_values(":pk", AttributeValue::S(pk))
            .expression_attribute_values(":mfg", AttributeValue::S(manufacturer.into()))
            .expression_attribute_values(":name", AttributeValue::S(product_name.into()))
            .limit(1)
            .send()
            .await
            .map_err(Box::new)?;

        Ok(result.count() > 0)
    }

    /// Get product categories with counts.
    pub async fn get_categories(&self) -> Result<Vec<serde_json::Value>, DbError> {
        let all_products = self.list_products(None, None).await?;

        let mut count_map: HashMap<ProductType, usize> = HashMap::new();
        for product in &all_products {
            *count_map.entry(product.product_type()).or_default() += 1;
        }

        let categories: Vec<serde_json::Value> = VALID_PRODUCT_TYPES
            .iter()
            .map(|pt| {
                let count = count_map.get(pt).copied().unwrap_or(0);
                serde_json::json!({
                    "type": pt.as_str(),
                    "count": count,
                    "display_name": format!("{}s", pt.display_name()),
                })
            })
            .collect();

        Ok(categories)
    }

    /// Get summary statistics.
    pub async fn get_summary(&self) -> Result<serde_json::Value, DbError> {
        let categories = self.get_categories().await?;
        let total: usize = categories
            .iter()
            .filter_map(|c| c["count"].as_u64())
            .sum::<u64>() as usize;

        let mut summary = serde_json::json!({ "total": total });
        for cat in &categories {
            let key = format!("{}s", cat["type"].as_str().unwrap_or("unknown"));
            summary[key] = cat["count"].clone();
        }

        Ok(summary)
    }

    /// Get unique manufacturer names.
    pub async fn get_unique_manufacturers(&self) -> Result<Vec<String>, DbError> {
        let products = self.list_products(None, None).await?;
        let mut manufacturers: Vec<String> = products
            .iter()
            .filter_map(|p| p.base().manufacturer.clone())
            .collect::<std::collections::HashSet<_>>()
            .into_iter()
            .collect();
        manufacturers.sort();
        Ok(manufacturers)
    }

    /// Get unique product names.
    pub async fn get_unique_names(&self) -> Result<Vec<String>, DbError> {
        let products = self.list_products(None, None).await?;
        let mut names: Vec<String> = products
            .iter()
            .map(|p| p.base().product_name.clone())
            .collect::<std::collections::HashSet<_>>()
            .into_iter()
            .collect();
        names.sort();
        Ok(names)
    }

    // -----------------------------------------------------------------------
    // Batch operations
    // -----------------------------------------------------------------------

    /// Batch create products (25 per batch, matching DynamoDB limit).
    pub async fn batch_create_products(&self, products: &[Product]) -> Result<usize, DbError> {
        if products.is_empty() {
            return Ok(0);
        }

        let mut success_count = 0;

        for chunk in products.chunks(25) {
            let mut requests = Vec::new();
            for product in chunk {
                let mut json = serde_json::to_value(product)
                    .map_err(|e| DbError::Serialization(e.to_string()))?;
                let obj = json.as_object_mut().unwrap();
                obj.insert("PK".into(), serde_json::Value::String(product.pk()));
                obj.insert("SK".into(), serde_json::Value::String(product.sk()));

                match to_dynamo_item(&json) {
                    Ok(item) => {
                        let request = aws_sdk_dynamodb::types::WriteRequest::builder()
                            .put_request(
                                aws_sdk_dynamodb::types::PutRequest::builder()
                                    .set_item(Some(item))
                                    .build()
                                    .map_err(|e| DbError::Serialization(e.to_string()))?,
                            )
                            .build();
                        requests.push(request);
                    }
                    Err(e) => {
                        error!("Failed to serialize product: {}", e);
                        continue;
                    }
                }
            }

            if requests.is_empty() {
                continue;
            }

            self.client
                .batch_write_item()
                .request_items(&self.table_name, requests.clone())
                .send()
                .await
                .map_err(Box::new)?;

            success_count += requests.len();
        }

        info!("Batch created {} products", success_count);
        Ok(success_count)
    }

    /// Batch delete items by PK/SK pairs.
    pub async fn batch_delete(&self, keys: &[(String, String)]) -> Result<usize, DbError> {
        if keys.is_empty() {
            return Ok(0);
        }

        let mut deleted = 0;

        for chunk in keys.chunks(25) {
            let requests: Vec<_> = chunk
                .iter()
                .map(|(pk, sk)| {
                    aws_sdk_dynamodb::types::WriteRequest::builder()
                        .delete_request(
                            aws_sdk_dynamodb::types::DeleteRequest::builder()
                                .key("PK", AttributeValue::S(pk.clone()))
                                .key("SK", AttributeValue::S(sk.clone()))
                                .build()
                                .unwrap(),
                        )
                        .build()
                })
                .collect();

            self.client
                .batch_write_item()
                .request_items(&self.table_name, requests.clone())
                .send()
                .await
                .map_err(Box::new)?;

            deleted += requests.len();
        }

        Ok(deleted)
    }

    // -----------------------------------------------------------------------
    // Datasheet operations
    // -----------------------------------------------------------------------

    /// Create a datasheet entry.
    pub async fn create_datasheet(&self, datasheet: &Datasheet) -> Result<(), DbError> {
        let mut json =
            serde_json::to_value(datasheet).map_err(|e| DbError::Serialization(e.to_string()))?;

        let obj = json.as_object_mut().unwrap();
        obj.insert("PK".into(), serde_json::Value::String(datasheet.pk()));
        obj.insert("SK".into(), serde_json::Value::String(datasheet.sk()));

        let item = to_dynamo_item(&json)?;
        self.client
            .put_item()
            .table_name(&self.table_name)
            .set_item(Some(item))
            .send()
            .await
            .map_err(Box::new)?;

        Ok(())
    }

    /// List all datasheets (scan with PK prefix filter).
    pub async fn list_datasheets(&self) -> Result<Vec<Datasheet>, DbError> {
        let mut datasheets = Vec::new();
        let mut exclusive_start_key: Option<HashMap<String, AttributeValue>> = None;

        loop {
            let mut scan = self
                .client
                .scan()
                .table_name(&self.table_name)
                .filter_expression("begins_with(PK, :pk)")
                .expression_attribute_values(":pk", AttributeValue::S("DATASHEET#".into()));

            if let Some(ref key) = exclusive_start_key {
                scan = scan.set_exclusive_start_key(Some(key.clone()));
            }

            let result = scan.send().await.map_err(Box::new)?;

            if let Some(items) = result.items {
                for item in &items {
                    let json = from_dynamo_item(item);
                    match serde_json::from_value::<Datasheet>(json) {
                        Ok(ds) => datasheets.push(ds),
                        Err(e) => warn!("Skipping undeserializable datasheet: {}", e),
                    }
                }
            }

            if result.last_evaluated_key.is_none() {
                break;
            }
            exclusive_start_key = result.last_evaluated_key;
        }

        Ok(datasheets)
    }

    /// Check if a datasheet with the given URL exists.
    pub async fn datasheet_exists(&self, url: &str) -> Result<bool, DbError> {
        let result = self
            .client
            .scan()
            .table_name(&self.table_name)
            .filter_expression("#url = :url")
            .expression_attribute_names("#url", "url")
            .expression_attribute_values(":url", AttributeValue::S(url.into()))
            .limit(1)
            .send()
            .await
            .map_err(Box::new)?;

        Ok(!result.items.unwrap_or_default().is_empty())
    }

    /// Delete a datasheet by ID and type.
    pub async fn delete_datasheet(
        &self,
        datasheet_id: &str,
        product_type: ProductType,
    ) -> Result<(), DbError> {
        let pk = format!("DATASHEET#{}", product_type.as_str().to_uppercase());
        let sk = format!("DATASHEET#{}", datasheet_id);

        self.client
            .delete_item()
            .table_name(&self.table_name)
            .key("PK", AttributeValue::S(pk))
            .key("SK", AttributeValue::S(sk))
            .send()
            .await
            .map_err(Box::new)?;

        Ok(())
    }

    /// Update a datasheet (read-modify-write).
    pub async fn update_datasheet(
        &self,
        datasheet_id: &str,
        product_type: ProductType,
        updates: serde_json::Value,
    ) -> Result<bool, DbError> {
        let pk = format!("DATASHEET#{}", product_type.as_str().to_uppercase());
        let sk = format!("DATASHEET#{}", datasheet_id);

        let result = self
            .client
            .get_item()
            .table_name(&self.table_name)
            .key("PK", AttributeValue::S(pk.clone()))
            .key("SK", AttributeValue::S(sk.clone()))
            .send()
            .await
            .map_err(Box::new)?;

        let Some(existing_item) = result.item else {
            return Ok(false);
        };

        let mut json = from_dynamo_item(&existing_item);
        if let (Some(base), Some(upd)) = (json.as_object_mut(), updates.as_object()) {
            for (k, v) in upd {
                base.insert(k.clone(), v.clone());
            }
            base.insert("PK".into(), serde_json::Value::String(pk));
            base.insert("SK".into(), serde_json::Value::String(sk));
        }

        let item = to_dynamo_item(&json)?;
        self.client
            .put_item()
            .table_name(&self.table_name)
            .set_item(Some(item))
            .send()
            .await
            .map_err(Box::new)?;

        Ok(true)
    }

    // -----------------------------------------------------------------------
    // Bulk delete operations
    // -----------------------------------------------------------------------

    /// Delete all items in the table. Returns count deleted.
    pub async fn delete_all(&self, dry_run: bool) -> Result<usize, DbError> {
        let mut keys = Vec::new();
        let mut exclusive_start_key: Option<HashMap<String, AttributeValue>> = None;

        loop {
            let mut scan = self
                .client
                .scan()
                .table_name(&self.table_name)
                .projection_expression("PK, SK");

            if let Some(ref key) = exclusive_start_key {
                scan = scan.set_exclusive_start_key(Some(key.clone()));
            }

            let result = scan.send().await.map_err(Box::new)?;

            if let Some(items) = result.items {
                for item in &items {
                    if let (Some(AttributeValue::S(pk)), Some(AttributeValue::S(sk))) =
                        (item.get("PK"), item.get("SK"))
                    {
                        keys.push((pk.clone(), sk.clone()));
                    }
                }
            }

            if result.last_evaluated_key.is_none() {
                break;
            }
            exclusive_start_key = result.last_evaluated_key;
        }

        info!("Found {} items in table", keys.len());

        if dry_run {
            return Ok(keys.len());
        }

        let deleted = self.batch_delete(&keys).await?;
        info!("Deleted {} items", deleted);
        Ok(deleted)
    }

    /// Delete all products of a specific type. Returns count deleted.
    pub async fn delete_by_product_type(
        &self,
        product_type: ProductType,
        dry_run: bool,
    ) -> Result<usize, DbError> {
        let pk = format!("PRODUCT#{}", product_type.as_str().to_uppercase());
        let mut keys = Vec::new();
        let mut exclusive_start_key: Option<HashMap<String, AttributeValue>> = None;

        loop {
            let mut query = self
                .client
                .query()
                .table_name(&self.table_name)
                .key_condition_expression("PK = :pk")
                .expression_attribute_values(":pk", AttributeValue::S(pk.clone()))
                .projection_expression("PK, SK");

            if let Some(ref key) = exclusive_start_key {
                query = query.set_exclusive_start_key(Some(key.clone()));
            }

            let result = query.send().await.map_err(Box::new)?;

            if let Some(items) = result.items {
                for item in &items {
                    if let (Some(AttributeValue::S(pk)), Some(AttributeValue::S(sk))) =
                        (item.get("PK"), item.get("SK"))
                    {
                        keys.push((pk.clone(), sk.clone()));
                    }
                }
            }

            if result.last_evaluated_key.is_none() {
                break;
            }
            exclusive_start_key = result.last_evaluated_key;
        }

        info!("Found {} {} products", keys.len(), product_type);

        if dry_run {
            return Ok(keys.len());
        }

        self.batch_delete(&keys).await
    }

    /// Get datasheets by product name.
    pub async fn get_datasheets_by_product_name(
        &self,
        product_name: &str,
    ) -> Result<Vec<Datasheet>, DbError> {
        let all = self.list_datasheets().await?;
        Ok(all
            .into_iter()
            .filter(|ds| ds.product_name == product_name)
            .collect())
    }

    /// Get datasheets by product family.
    pub async fn get_datasheets_by_family(&self, family: &str) -> Result<Vec<Datasheet>, DbError> {
        let all = self.list_datasheets().await?;
        Ok(all
            .into_iter()
            .filter(|ds| ds.product_family.as_deref() == Some(family))
            .collect())
    }
}
