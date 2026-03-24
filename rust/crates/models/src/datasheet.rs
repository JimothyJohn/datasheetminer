//! Datasheet entity model.

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::common::ProductType;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Datasheet {
    #[serde(default = "Uuid::new_v4")]
    pub datasheet_id: Uuid,
    pub url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pages: Option<Vec<i32>>,
    pub product_type: ProductType,
    pub product_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub product_family: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manufacturer: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub category: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub release_year: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warranty: Option<String>,
}

impl Datasheet {
    pub fn pk(&self) -> String {
        format!("DATASHEET#{}", self.product_type.as_str().to_uppercase())
    }

    pub fn sk(&self) -> String {
        format!("DATASHEET#{}", self.datasheet_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_datasheet_pk_sk() {
        let ds = Datasheet {
            datasheet_id: Uuid::parse_str("12345678-1234-1234-1234-123456789012").unwrap(),
            url: "https://example.com/spec.pdf".into(),
            pages: None,
            product_type: ProductType::Motor,
            product_name: "Test".into(),
            product_family: None,
            manufacturer: None,
            category: None,
            release_year: None,
            warranty: None,
        };
        assert_eq!(ds.pk(), "DATASHEET#MOTOR");
        assert_eq!(ds.sk(), "DATASHEET#12345678-1234-1234-1234-123456789012");
    }
}
