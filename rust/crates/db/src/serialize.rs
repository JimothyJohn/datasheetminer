//! Serialization between Rust models and DynamoDB AttributeValue maps.
//!
//! Handles the bidirectional conversion:
//! - Write path: model → JSON → parse compact "value;unit" strings into
//!   structured `{value: N, unit: S}` maps → DynamoDB AttributeValues
//! - Read path: DynamoDB AttributeValues → JSON (with structured maps) →
//!   model (which accepts both compact strings and {value,unit} dicts)

use std::collections::HashMap;

use aws_sdk_dynamodb::types::AttributeValue;
use serde_json::Value;

use crate::error::DbError;

/// Convert a serde_json::Value to a DynamoDB AttributeValue.
pub fn json_to_attr(value: &Value) -> AttributeValue {
    match value {
        Value::Null => AttributeValue::Null(true),
        Value::Bool(b) => AttributeValue::Bool(*b),
        Value::Number(n) => AttributeValue::N(n.to_string()),
        Value::String(s) => {
            if s.is_empty() {
                // DynamoDB doesn't allow empty strings in some contexts
                AttributeValue::Null(true)
            } else if s.contains(';') {
                // Parse compact "value;unit" or "min-max;unit" into structured map
                parse_compact_unit_to_attr(s)
            } else {
                AttributeValue::S(s.clone())
            }
        }
        Value::Array(arr) => {
            let items: Vec<AttributeValue> = arr.iter().map(json_to_attr).collect();
            AttributeValue::L(items)
        }
        Value::Object(obj) => {
            let mut map = HashMap::new();
            for (k, v) in obj {
                // Skip null values (matching Python's exclude_none=True)
                if !v.is_null() {
                    map.insert(k.clone(), json_to_attr(v));
                }
            }
            AttributeValue::M(map)
        }
    }
}

/// Parse a compact "value;unit" string into a structured DynamoDB map.
///
/// Matches Python's `_parse_compact_units`:
/// - "20;C" → {value: 20, unit: "C"}
/// - "20-40;C" → {min: 20, max: 40, unit: "C"}
/// - "-20-40;C" → {min: -20, max: 40, unit: "C"}
/// - Non-matching strings pass through as plain strings.
fn parse_compact_unit_to_attr(s: &str) -> AttributeValue {
    let Some((value_part, unit)) = s.split_once(';') else {
        return AttributeValue::S(s.to_string());
    };

    // Try range pattern first
    if let Some((min_str, max_str)) = split_range(value_part) {
        if let (Ok(_), Ok(_)) = (min_str.parse::<f64>(), max_str.parse::<f64>()) {
            let mut map = HashMap::new();
            map.insert("min".into(), AttributeValue::N(min_str.to_string()));
            map.insert("max".into(), AttributeValue::N(max_str.to_string()));
            map.insert("unit".into(), AttributeValue::S(unit.to_string()));
            return AttributeValue::M(map);
        }
    }

    // Try single value
    if value_part.parse::<f64>().is_ok() {
        let mut map = HashMap::new();
        map.insert("value".into(), AttributeValue::N(value_part.to_string()));
        map.insert("unit".into(), AttributeValue::S(unit.to_string()));
        return AttributeValue::M(map);
    }

    // Non-numeric value (e.g., "2+;Years") — store as plain string
    AttributeValue::S(s.to_string())
}

/// Split a range value like "20-40" or "-20-40" into (min, max).
fn split_range(value_part: &str) -> Option<(&str, &str)> {
    let search_start = if value_part.starts_with('-') { 1 } else { 0 };
    let rest = &value_part[search_start..];
    if let Some(dash_pos) = rest.find('-') {
        let abs_pos = search_start + dash_pos;
        let min_str = &value_part[..abs_pos];
        let max_str = &value_part[abs_pos + 1..];
        if !min_str.is_empty() && !max_str.is_empty() {
            return Some((min_str, max_str));
        }
    }
    None
}

/// Convert a DynamoDB AttributeValue to serde_json::Value.
///
/// Structured `{value, unit}` and `{min, max, unit}` maps are converted
/// back to compact "value;unit" strings so the Rust models can deserialize them.
pub fn attr_to_json(attr: &AttributeValue) -> Value {
    match attr {
        AttributeValue::S(s) => Value::String(s.clone()),
        AttributeValue::N(n) => {
            // Try integer first, then float
            if let Ok(i) = n.parse::<i64>() {
                Value::Number(i.into())
            } else if let Ok(f) = n.parse::<f64>() {
                serde_json::Number::from_f64(f)
                    .map(Value::Number)
                    .unwrap_or(Value::String(n.clone()))
            } else {
                Value::String(n.clone())
            }
        }
        AttributeValue::Bool(b) => Value::Bool(*b),
        AttributeValue::Null(_) => Value::Null,
        AttributeValue::L(items) => Value::Array(items.iter().map(attr_to_json).collect()),
        AttributeValue::M(map) => {
            // Check if this is a structured ValueUnit or MinMaxUnit
            if let Some(compact) = try_compact_unit_map(map) {
                return Value::String(compact);
            }
            // Regular object
            let obj: serde_json::Map<String, Value> = map
                .iter()
                .map(|(k, v)| (k.clone(), attr_to_json(v)))
                .collect();
            Value::Object(obj)
        }
        // SS, NS, BS etc. — not used in our schema
        _ => Value::Null,
    }
}

/// Try to convert a structured {value, unit} or {min, max, unit} map
/// back to a compact "value;unit" string.
fn try_compact_unit_map(map: &HashMap<String, AttributeValue>) -> Option<String> {
    let unit = match map.get("unit") {
        Some(AttributeValue::S(u)) => u,
        _ => return None,
    };

    // {min, max, unit} → "min-max;unit"
    if let (Some(AttributeValue::N(min)), Some(AttributeValue::N(max))) =
        (map.get("min"), map.get("max"))
    {
        if map.len() == 3 {
            return Some(format!("{}-{};{}", min, max, unit));
        }
    }

    // {value, unit} → "value;unit"
    if let Some(AttributeValue::N(val)) = map.get("value") {
        if map.len() == 2 {
            return Some(format!("{};{}", val, unit));
        }
    }

    None
}

/// Serialize a Rust model (as JSON Value) into a DynamoDB item HashMap.
pub fn to_dynamo_item(json: &Value) -> Result<HashMap<String, AttributeValue>, DbError> {
    match json {
        Value::Object(obj) => {
            let mut item = HashMap::new();
            for (k, v) in obj {
                if !v.is_null() {
                    item.insert(k.clone(), json_to_attr(v));
                }
            }
            Ok(item)
        }
        _ => Err(DbError::Serialization(
            "Expected JSON object for DynamoDB item".into(),
        )),
    }
}

/// Deserialize a DynamoDB item HashMap into a JSON Value.
pub fn from_dynamo_item(item: &HashMap<String, AttributeValue>) -> Value {
    let obj: serde_json::Map<String, Value> = item
        .iter()
        .map(|(k, v)| (k.clone(), attr_to_json(v)))
        .collect();
    Value::Object(obj)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_single_value_unit_roundtrip() {
        let input = Value::String("3000;rpm".into());
        let attr = json_to_attr(&input);

        // Should be structured map in DynamoDB
        if let AttributeValue::M(map) = &attr {
            assert!(map.contains_key("value"));
            assert!(map.contains_key("unit"));
            assert_eq!(map.get("unit"), Some(&AttributeValue::S("rpm".into())));
        } else {
            panic!("Expected M, got {:?}", attr);
        }

        // Convert back to JSON
        let output = attr_to_json(&attr);
        assert_eq!(output, Value::String("3000;rpm".into()));
    }

    #[test]
    fn test_range_unit_roundtrip() {
        let input = Value::String("200-240;V".into());
        let attr = json_to_attr(&input);

        if let AttributeValue::M(map) = &attr {
            assert!(map.contains_key("min"));
            assert!(map.contains_key("max"));
            assert!(map.contains_key("unit"));
        } else {
            panic!("Expected M, got {:?}", attr);
        }

        let output = attr_to_json(&attr);
        assert_eq!(output, Value::String("200-240;V".into()));
    }

    #[test]
    fn test_negative_range_roundtrip() {
        let input = Value::String("-20-40;C".into());
        let attr = json_to_attr(&input);

        if let AttributeValue::M(map) = &attr {
            assert_eq!(map.get("min"), Some(&AttributeValue::N("-20".into())));
            assert_eq!(map.get("max"), Some(&AttributeValue::N("40".into())));
        } else {
            panic!("Expected M");
        }

        let output = attr_to_json(&attr);
        assert_eq!(output, Value::String("-20-40;C".into()));
    }

    #[test]
    fn test_non_numeric_value_stays_string() {
        let input = Value::String("2+;Years".into());
        let attr = json_to_attr(&input);
        assert!(matches!(attr, AttributeValue::S(_)));
    }

    #[test]
    fn test_plain_string_no_semicolon() {
        let input = Value::String("hello".into());
        let attr = json_to_attr(&input);
        assert_eq!(attr, AttributeValue::S("hello".into()));
    }

    #[test]
    fn test_number() {
        let input = serde_json::json!(42);
        let attr = json_to_attr(&input);
        assert_eq!(attr, AttributeValue::N("42".into()));
    }

    #[test]
    fn test_bool() {
        let input = Value::Bool(true);
        let attr = json_to_attr(&input);
        assert_eq!(attr, AttributeValue::Bool(true));
    }

    #[test]
    fn test_null() {
        let attr = json_to_attr(&Value::Null);
        assert_eq!(attr, AttributeValue::Null(true));
    }

    #[test]
    fn test_nested_object() {
        let input = serde_json::json!({
            "width": 100.0,
            "unit": "mm"
        });
        let attr = json_to_attr(&input);
        if let AttributeValue::M(map) = attr {
            assert!(map.contains_key("width"));
            assert!(map.contains_key("unit"));
        } else {
            panic!("Expected M");
        }
    }

    #[test]
    fn test_list() {
        let input = serde_json::json!(["a", "b"]);
        let attr = json_to_attr(&input);
        if let AttributeValue::L(items) = attr {
            assert_eq!(items.len(), 2);
        } else {
            panic!("Expected L");
        }
    }

    #[test]
    fn test_full_product_roundtrip() {
        let product_json = serde_json::json!({
            "product_type": "motor",
            "product_name": "Test",
            "rated_speed": "3000;rpm",
            "rated_voltage": "200-240;V",
            "poles": 8
        });

        let item = to_dynamo_item(&product_json).unwrap();
        let back = from_dynamo_item(&item);
        let back_obj = back.as_object().unwrap();

        assert_eq!(back_obj["product_type"], "motor");
        assert_eq!(back_obj["product_name"], "Test");
        assert_eq!(back_obj["rated_speed"], "3000;rpm");
        assert_eq!(back_obj["rated_voltage"], "200-240;V");
        assert_eq!(back_obj["poles"], 8);
    }
}
