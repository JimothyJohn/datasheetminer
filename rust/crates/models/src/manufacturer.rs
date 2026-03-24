//! Manufacturer entity model.

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Manufacturer {
    #[serde(default = "Uuid::new_v4")]
    pub id: Uuid,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub website: Option<String>,
    #[serde(default)]
    pub offered_product_types: Vec<String>,
}

impl Manufacturer {
    pub fn pk(&self) -> &'static str {
        "MANUFACTURER"
    }

    pub fn sk(&self) -> String {
        format!("MANUFACTURER#{}", self.id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_manufacturer_pk_sk() {
        let mfg = Manufacturer {
            id: Uuid::parse_str("12345678-1234-1234-1234-123456789012").unwrap(),
            name: "Delta Electronics".into(),
            website: Some("https://www.delta.com".into()),
            offered_product_types: vec!["motor".into(), "drive".into()],
        };
        assert_eq!(mfg.pk(), "MANUFACTURER");
        assert_eq!(
            mfg.sk(),
            "MANUFACTURER#12345678-1234-1234-1234-123456789012"
        );
    }
}
