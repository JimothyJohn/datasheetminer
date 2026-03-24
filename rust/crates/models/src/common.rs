//! Shared types: ProductType, ValueUnit, MinMaxUnit.
//!
//! ValueUnit and MinMaxUnit use custom serde to accept multiple input forms
//! (string, dict, space-separated) and normalize units on deserialization.

use std::fmt;

use serde::de::{self, MapAccess, Visitor};
use serde::{Deserialize, Deserializer, Serialize, Serializer};

use dsm_units::normalize_value_unit;

/// All supported product types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProductType {
    Motor,
    Drive,
    Gearhead,
    RobotArm,
    Factory,
    Datasheet,
}

impl ProductType {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Motor => "motor",
            Self::Drive => "drive",
            Self::Gearhead => "gearhead",
            Self::RobotArm => "robot_arm",
            Self::Factory => "factory",
            Self::Datasheet => "datasheet",
        }
    }

    pub fn display_name(&self) -> &'static str {
        match self {
            Self::Motor => "Motor",
            Self::Drive => "Drive",
            Self::Gearhead => "Gearhead",
            Self::RobotArm => "Robot Arm",
            Self::Factory => "Factory",
            Self::Datasheet => "Datasheet",
        }
    }
}

impl fmt::Display for ProductType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

// ---------------------------------------------------------------------------
// ValueUnit — "value;unit" compact string with flexible deserialization
// ---------------------------------------------------------------------------

/// A value+unit pair stored as `"value;unit"` (e.g. `"3000;rpm"`).
///
/// Deserialization accepts:
/// - `"value;unit"` string
/// - `{"value": X, "unit": Y}` object
/// - `"value unit"` space-separated string
///
/// On deserialization, special chars `+~><` are stripped from the value,
/// and units are normalized to canonical forms via `dsm_units`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValueUnit(pub Option<String>);

impl ValueUnit {
    pub fn none() -> Self {
        Self(None)
    }

    pub fn as_str(&self) -> Option<&str> {
        self.0.as_deref()
    }

    /// Parse into (value_str, unit) components.
    pub fn parts(&self) -> Option<(&str, &str)> {
        self.0.as_deref()?.split_once(';')
    }
}

impl Serialize for ValueUnit {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match &self.0 {
            Some(s) => serializer.serialize_str(s),
            None => serializer.serialize_none(),
        }
    }
}

impl<'de> Deserialize<'de> for ValueUnit {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        deserializer.deserialize_any(ValueUnitVisitor)
    }
}

struct ValueUnitVisitor;

impl<'de> Visitor<'de> for ValueUnitVisitor {
    type Value = ValueUnit;

    fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
        f.write_str(
            "null, a \"value;unit\" string, a \"value unit\" string, or a {value, unit} object",
        )
    }

    fn visit_none<E: de::Error>(self) -> Result<Self::Value, E> {
        Ok(ValueUnit(None))
    }

    fn visit_unit<E: de::Error>(self) -> Result<Self::Value, E> {
        Ok(ValueUnit(None))
    }

    fn visit_str<E: de::Error>(self, v: &str) -> Result<Self::Value, E> {
        Ok(ValueUnit(Some(parse_value_unit_string(v))))
    }

    fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Self::Value, M::Error> {
        let mut value: Option<String> = None;
        let mut unit: Option<String> = None;

        while let Some(key) = map.next_key::<String>()? {
            match key.as_str() {
                "value" => value = map.next_value()?,
                "unit" => unit = map.next_value()?,
                _ => {
                    let _ = map.next_value::<serde_json::Value>()?;
                }
            }
        }

        match (value, unit) {
            (Some(v), Some(u)) => {
                let clean_val = strip_special_chars(&v);
                let compact = format!("{};{}", clean_val, u);
                let normalized = normalize_value_unit(&compact);
                Ok(ValueUnit(Some(normalized)))
            }
            _ => Ok(ValueUnit(None)),
        }
    }
}

// ---------------------------------------------------------------------------
// MinMaxUnit — "min-max;unit" compact string
// ---------------------------------------------------------------------------

/// A range+unit pair stored as `"min-max;unit"` (e.g. `"200-240;V"`).
///
/// Also accepts single values like `"200;V"`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MinMaxUnit(pub Option<String>);

impl MinMaxUnit {
    pub fn none() -> Self {
        Self(None)
    }

    pub fn as_str(&self) -> Option<&str> {
        self.0.as_deref()
    }
}

impl Serialize for MinMaxUnit {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match &self.0 {
            Some(s) => serializer.serialize_str(s),
            None => serializer.serialize_none(),
        }
    }
}

impl<'de> Deserialize<'de> for MinMaxUnit {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        deserializer.deserialize_any(MinMaxUnitVisitor)
    }
}

struct MinMaxUnitVisitor;

impl<'de> Visitor<'de> for MinMaxUnitVisitor {
    type Value = MinMaxUnit;

    fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
        f.write_str("null, a \"range;unit\" string, or a {min, max, unit} object")
    }

    fn visit_none<E: de::Error>(self) -> Result<Self::Value, E> {
        Ok(MinMaxUnit(None))
    }

    fn visit_unit<E: de::Error>(self) -> Result<Self::Value, E> {
        Ok(MinMaxUnit(None))
    }

    fn visit_str<E: de::Error>(self, v: &str) -> Result<Self::Value, E> {
        Ok(MinMaxUnit(Some(parse_min_max_unit_string(v))))
    }

    fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Self::Value, M::Error> {
        let mut min: Option<String> = None;
        let mut max: Option<String> = None;
        let mut unit: Option<String> = None;

        while let Some(key) = map.next_key::<String>()? {
            match key.as_str() {
                "min" => min = map.next_value()?,
                "max" => max = map.next_value()?,
                "unit" => unit = map.next_value()?,
                _ => {
                    let _ = map.next_value::<serde_json::Value>()?;
                }
            }
        }

        let Some(u) = unit else {
            return Ok(MinMaxUnit(None));
        };

        let compact = match (min, max) {
            (Some(mn), Some(mx)) => format!("{}-{};{}", mn, mx, u),
            (Some(mn), None) => format!("{};{}", mn, u),
            (None, Some(mx)) => format!("{};{}", mx, u),
            (None, None) => return Ok(MinMaxUnit(None)),
        };

        let normalized = normalize_value_unit(&compact);
        Ok(MinMaxUnit(Some(normalized)))
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Strip `+`, `~`, `>`, `<` from value strings (LLM artifacts).
fn strip_special_chars(s: &str) -> String {
    s.trim().replace(['+', '~', '>', '<'], "")
}

/// Parse a ValueUnit string: handle both "value;unit" and "value unit" forms.
fn parse_value_unit_string(v: &str) -> String {
    if v.contains(';') {
        // "val;unit" form — clean value and normalize
        if let Some((val, unit)) = v.split_once(';') {
            let clean = strip_special_chars(val);
            let compact = format!("{};{}", clean, unit);
            return normalize_value_unit(&compact);
        }
    }

    // Try space-separated "value unit"
    let parts: Vec<&str> = v.trim().splitn(2, ' ').collect();
    if parts.len() == 2 {
        let clean = strip_special_chars(parts[0]);
        let compact = format!("{};{}", clean, parts[1]);
        return normalize_value_unit(&compact);
    }

    v.to_string()
}

/// Parse a MinMaxUnit string, handling "to" separator.
fn parse_min_max_unit_string(v: &str) -> String {
    // Replace " to " with "-"
    let cleaned = v.replace(" to ", "-");

    if let Some((range_part, unit)) = cleaned.split_once(';') {
        let compact = format!("{};{}", range_part.trim(), unit);
        return normalize_value_unit(&compact);
    }

    cleaned
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_product_type_serde_roundtrip() {
        let pt = ProductType::RobotArm;
        let json = serde_json::to_string(&pt).unwrap();
        assert_eq!(json, r#""robot_arm""#);
        let parsed: ProductType = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, ProductType::RobotArm);
    }

    #[test]
    fn test_product_type_as_str() {
        assert_eq!(ProductType::Motor.as_str(), "motor");
        assert_eq!(ProductType::RobotArm.as_str(), "robot_arm");
    }

    // --- ValueUnit ---
    #[test]
    fn test_value_unit_from_string() {
        let vu: ValueUnit = serde_json::from_str(r#""3000;rpm""#).unwrap();
        assert_eq!(vu.as_str(), Some("3000;rpm"));
    }

    #[test]
    fn test_value_unit_from_dict() {
        let vu: ValueUnit = serde_json::from_str(r#"{"value": "3000", "unit": "rpm"}"#).unwrap();
        assert_eq!(vu.as_str(), Some("3000;rpm"));
    }

    #[test]
    fn test_value_unit_from_space_separated() {
        let vu: ValueUnit = serde_json::from_str(r#""3000 rpm""#).unwrap();
        assert_eq!(vu.as_str(), Some("3000;rpm"));
    }

    #[test]
    fn test_value_unit_null() {
        let vu: ValueUnit = serde_json::from_str("null").unwrap();
        assert_eq!(vu, ValueUnit(None));
    }

    #[test]
    fn test_value_unit_strips_special_chars() {
        let vu: ValueUnit = serde_json::from_str(r#""+3000;rpm""#).unwrap();
        assert_eq!(vu.as_str(), Some("3000;rpm"));
    }

    #[test]
    fn test_value_unit_normalizes_units() {
        let vu: ValueUnit = serde_json::from_str(r#""500;mNm""#).unwrap();
        assert_eq!(vu.as_str(), Some("0.5;Nm"));
    }

    #[test]
    fn test_value_unit_dict_normalizes() {
        let vu: ValueUnit = serde_json::from_str(r#"{"value": "500", "unit": "mNm"}"#).unwrap();
        assert_eq!(vu.as_str(), Some("0.5;Nm"));
    }

    #[test]
    fn test_value_unit_parts() {
        let vu = ValueUnit(Some("3000;rpm".into()));
        let (val, unit) = vu.parts().unwrap();
        assert_eq!(val, "3000");
        assert_eq!(unit, "rpm");
    }

    #[test]
    fn test_value_unit_serialize() {
        let vu = ValueUnit(Some("3000;rpm".into()));
        let json = serde_json::to_string(&vu).unwrap();
        assert_eq!(json, r#""3000;rpm""#);
    }

    #[test]
    fn test_value_unit_serialize_none() {
        let vu = ValueUnit(None);
        let json = serde_json::to_string(&vu).unwrap();
        assert_eq!(json, "null");
    }

    // --- MinMaxUnit ---
    #[test]
    fn test_min_max_unit_from_string() {
        let mmu: MinMaxUnit = serde_json::from_str(r#""200-240;V""#).unwrap();
        assert_eq!(mmu.as_str(), Some("200-240;V"));
    }

    #[test]
    fn test_min_max_unit_from_dict() {
        let mmu: MinMaxUnit =
            serde_json::from_str(r#"{"min": "200", "max": "240", "unit": "V"}"#).unwrap();
        assert_eq!(mmu.as_str(), Some("200-240;V"));
    }

    #[test]
    fn test_min_max_unit_min_only() {
        let mmu: MinMaxUnit = serde_json::from_str(r#"{"min": "200", "unit": "V"}"#).unwrap();
        assert_eq!(mmu.as_str(), Some("200;V"));
    }

    #[test]
    fn test_min_max_unit_null() {
        let mmu: MinMaxUnit = serde_json::from_str("null").unwrap();
        assert_eq!(mmu, MinMaxUnit(None));
    }

    #[test]
    fn test_min_max_unit_to_separator() {
        let mmu: MinMaxUnit = serde_json::from_str(r#""200 to 240;V""#).unwrap();
        assert_eq!(mmu.as_str(), Some("200-240;V"));
    }

    #[test]
    fn test_min_max_unit_normalizes() {
        let mmu: MinMaxUnit = serde_json::from_str(r#""100-500;mA""#).unwrap();
        assert_eq!(mmu.as_str(), Some("0.1-0.5;A"));
    }
}
