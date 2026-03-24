//! Askama custom filters for template rendering.

/// Convert snake_case to Title Case, with acronym handling.
pub fn format_label(s: &str) -> askama::Result<String> {
    let acronyms = ["ip", "ac", "dc", "pwm", "io", "tcp", "usb", "can"];
    let result = s
        .split('_')
        .map(|word| {
            if acronyms.contains(&word) {
                word.to_uppercase()
            } else {
                let mut chars = word.chars();
                match chars.next() {
                    None => String::new(),
                    Some(c) => c.to_uppercase().to_string() + chars.as_str(),
                }
            }
        })
        .collect::<Vec<_>>()
        .join(" ");
    Ok(result)
}

/// Format a spec value for display.
/// Handles "value;unit" → "value unit" and nested structures.
pub fn format_spec(v: &serde_json::Value) -> askama::Result<String> {
    match v {
        serde_json::Value::Null => Ok("—".into()),
        serde_json::Value::Bool(b) => Ok(if *b { "Yes" } else { "No" }.into()),
        serde_json::Value::Number(n) => Ok(n.to_string()),
        serde_json::Value::String(s) => {
            if let Some((val, unit)) = s.split_once(';') {
                Ok(format!("{} {}", val, unit))
            } else {
                Ok(s.clone())
            }
        }
        serde_json::Value::Array(arr) => {
            let items: Vec<String> = arr.iter().filter_map(|v| format_spec(v).ok()).collect();
            Ok(items.join(", "))
        }
        serde_json::Value::Object(obj) => {
            // Handle {value, unit} or {min, max, unit}
            if let Some(unit) = obj.get("unit").and_then(|u| u.as_str()) {
                if let (Some(min), Some(max)) = (
                    obj.get("min").and_then(|v| v.as_f64()),
                    obj.get("max").and_then(|v| v.as_f64()),
                ) {
                    return Ok(format!("{}-{} {}", min, max, unit));
                }
                if let Some(val) = obj.get("value").and_then(|v| v.as_f64()) {
                    return Ok(format!("{} {}", val, unit));
                }
            }
            // Generic object: key: value pairs
            let pairs: Vec<String> = obj
                .iter()
                .map(|(k, v)| {
                    let formatted = format_spec(v).unwrap_or_default();
                    format!("{}: {}", k, formatted)
                })
                .collect();
            Ok(pairs.join(", "))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_label() {
        assert_eq!(format_label("rated_speed").unwrap(), "Rated Speed");
        assert_eq!(format_label("ip_rating").unwrap(), "IP Rating");
        assert_eq!(format_label("max_tcp_speed").unwrap(), "Max TCP Speed");
    }

    #[test]
    fn test_format_spec_value_unit() {
        let v = serde_json::json!("3000;rpm");
        assert_eq!(format_spec(&v).unwrap(), "3000 rpm");
    }

    #[test]
    fn test_format_spec_number() {
        let v = serde_json::json!(42);
        assert_eq!(format_spec(&v).unwrap(), "42");
    }

    #[test]
    fn test_format_spec_null() {
        assert_eq!(format_spec(&serde_json::Value::Null).unwrap(), "—");
    }

    #[test]
    fn test_format_spec_array() {
        let v = serde_json::json!(["EtherCAT", "CANopen"]);
        assert_eq!(format_spec(&v).unwrap(), "EtherCAT, CANopen");
    }
}
