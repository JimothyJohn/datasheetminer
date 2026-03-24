//! ProductBase and the Product tagged-union enum.

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::common::{ProductType, ValueUnit};
use crate::drive::Drive;
use crate::gearhead::Gearhead;
use crate::motor::Motor;
use crate::robot_arm::RobotArm;

/// Physical dimensions (default unit: mm).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Dimensions {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub width: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub length: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<f64>,
    #[serde(default = "default_unit")]
    pub unit: Option<String>,
}

fn default_unit() -> Option<String> {
    Some("mm".into())
}

/// Fields shared by all tangible products.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProductBase {
    #[serde(default = "Uuid::new_v4")]
    pub product_id: Uuid,
    pub product_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub product_family: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub part_number: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manufacturer: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub release_year: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimensions: Option<Dimensions>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub weight: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub msrp: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warranty: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub datasheet_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pages: Option<Vec<i32>>,
}

impl ProductBase {
    /// DynamoDB partition key: `PRODUCT#{TYPE}`.
    pub fn pk(&self, product_type: ProductType) -> String {
        format!("PRODUCT#{}", product_type.as_str().to_uppercase())
    }

    /// DynamoDB sort key: `PRODUCT#{product_id}`.
    pub fn sk(&self) -> String {
        format!("PRODUCT#{}", self.product_id)
    }
}

/// Polymorphic product: tagged union on `product_type`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "product_type")]
pub enum Product {
    #[serde(rename = "motor")]
    Motor(Motor),
    #[serde(rename = "drive")]
    Drive(Drive),
    #[serde(rename = "gearhead")]
    Gearhead(Gearhead),
    #[serde(rename = "robot_arm")]
    RobotArm(Box<RobotArm>),
}

impl Product {
    pub fn product_type(&self) -> ProductType {
        match self {
            Self::Motor(_) => ProductType::Motor,
            Self::Drive(_) => ProductType::Drive,
            Self::Gearhead(_) => ProductType::Gearhead,
            Self::RobotArm(_) => ProductType::RobotArm,
        }
    }

    pub fn base(&self) -> &ProductBase {
        match self {
            Self::Motor(m) => &m.base,
            Self::Drive(d) => &d.base,
            Self::Gearhead(g) => &g.base,
            Self::RobotArm(r) => &r.base,
        }
    }

    pub fn base_mut(&mut self) -> &mut ProductBase {
        match self {
            Self::Motor(m) => &mut m.base,
            Self::Drive(d) => &mut d.base,
            Self::Gearhead(g) => &mut g.base,
            Self::RobotArm(r) => &mut r.base,
        }
    }

    pub fn pk(&self) -> String {
        self.base().pk(self.product_type())
    }

    pub fn sk(&self) -> String {
        self.base().sk()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_product_tagged_roundtrip() {
        let json = r#"{
            "product_type": "motor",
            "product_name": "Test Motor",
            "product_id": "12345678-1234-1234-1234-123456789012"
        }"#;
        let product: Product = serde_json::from_str(json).unwrap();
        assert_eq!(product.product_type(), ProductType::Motor);
        assert_eq!(product.base().product_name, "Test Motor");
    }

    #[test]
    fn test_product_pk_sk() {
        let json = r#"{
            "product_type": "drive",
            "product_name": "ASD-B3",
            "product_id": "12345678-1234-1234-1234-123456789012"
        }"#;
        let product: Product = serde_json::from_str(json).unwrap();
        assert_eq!(product.pk(), "PRODUCT#DRIVE");
        assert_eq!(product.sk(), "PRODUCT#12345678-1234-1234-1234-123456789012");
    }

    #[test]
    fn test_dimensions_default_unit() {
        let json = r#"{"width": 100.0}"#;
        let dims: Dimensions = serde_json::from_str(json).unwrap();
        assert_eq!(dims.unit, Some("mm".into()));
    }
}
