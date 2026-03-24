//! Product data quality scoring and filtering.
//!
//! Scores extracted products by how many spec fields are populated vs None.
//! Rejects products below a configurable threshold to prevent low-quality
//! entries from polluting the database.

use dsm_models::Product;
use tracing::{info, warn};

/// Minimum fraction of spec fields that must be populated (0.0–1.0).
pub const DEFAULT_MIN_QUALITY: f64 = 0.25;

/// Score result: (score 0.0–1.0, filled_count, total_count, missing_fields).
pub type ScoreResult = (f64, usize, usize, Vec<String>);

/// Known spec fields per product type (excluding meta fields).
/// Missing from the serialized JSON = None = unfilled.
fn spec_fields_for(product: &Product) -> &'static [&'static str] {
    match product {
        Product::Motor(_) => &[
            "type",
            "series",
            "rated_voltage",
            "rated_speed",
            "max_speed",
            "rated_torque",
            "peak_torque",
            "rated_power",
            "encoder_feedback_support",
            "poles",
            "rated_current",
            "peak_current",
            "voltage_constant",
            "torque_constant",
            "resistance",
            "inductance",
            "ip_rating",
            "rotor_inertia",
            "axial_load_force_rating",
            "radial_load_force_rating",
            "dimensions",
            "weight",
        ],
        Product::Drive(_) => &[
            "type",
            "series",
            "input_voltage",
            "input_voltage_frequency",
            "input_voltage_phases",
            "rated_current",
            "peak_current",
            "output_power",
            "switching_frequency",
            "fieldbus",
            "encoder_feedback_support",
            "ethernet_ports",
            "digital_inputs",
            "digital_outputs",
            "analog_inputs",
            "analog_outputs",
            "safety_rating",
            "approvals",
            "max_humidity",
            "ip_rating",
            "ambient_temp",
            "dimensions",
            "weight",
        ],
        Product::Gearhead(_) => &[
            "gear_ratio",
            "gear_type",
            "stages",
            "nominal_input_speed",
            "max_input_speed",
            "max_continuous_torque",
            "max_peak_torque",
            "backlash",
            "efficiency",
            "torsional_rigidity",
            "rotor_inertia",
            "noise_level",
            "frame_size",
            "input_shaft_diameter",
            "output_shaft_diameter",
            "max_radial_load",
            "max_axial_load",
            "ip_rating",
            "operating_temp",
            "service_life",
            "lubrication_type",
            "dimensions",
            "weight",
        ],
        Product::RobotArm(_) => &[
            "payload",
            "reach",
            "degrees_of_freedom",
            "pose_repeatability",
            "max_tcp_speed",
            "ip_rating",
            "cleanroom_class",
            "noise_level",
            "mounting_position",
            "operating_temp",
            "materials",
            "joints",
            "force_torque_sensor",
            "tool_io",
            "controller",
            "teach_pendant",
            "safety_certifications",
            "dimensions",
            "weight",
        ],
    }
}

/// Score a product's data completeness.
///
/// Checks known spec fields against the serialized JSON. Fields absent from
/// JSON (due to `skip_serializing_if`) are counted as missing.
pub fn score_product(product: &Product) -> ScoreResult {
    let json = serde_json::to_value(product).unwrap_or_default();
    let obj = match json.as_object() {
        Some(o) => o,
        None => return (1.0, 0, 0, vec![]),
    };

    let fields = spec_fields_for(product);
    let total = fields.len();
    if total == 0 {
        return (1.0, 0, 0, vec![]);
    }

    let mut missing = Vec::new();
    for &field in fields {
        match obj.get(field) {
            None | Some(serde_json::Value::Null) => missing.push(field.to_string()),
            _ => {}
        }
    }

    let filled = total - missing.len();
    let score = filled as f64 / total as f64;
    (score, filled, total, missing)
}

/// Partition products into those passing and failing the quality threshold.
pub fn filter_products(
    products: Vec<Product>,
    min_quality: Option<f64>,
) -> (Vec<Product>, Vec<Product>) {
    let threshold = min_quality.unwrap_or(DEFAULT_MIN_QUALITY);
    let mut passed = Vec::new();
    let mut rejected = Vec::new();

    for product in products {
        let (score, filled, total, missing) = score_product(&product);
        let part_id = product
            .base()
            .part_number
            .clone()
            .unwrap_or_else(|| product.base().product_name.clone());

        if score >= threshold {
            info!(
                "Quality PASS: '{}' — {}/{} fields ({:.0}%)",
                part_id,
                filled,
                total,
                score * 100.0
            );
            passed.push(product);
        } else {
            warn!(
                "Quality FAIL: '{}' — {}/{} fields ({:.0}%). Missing: {}",
                part_id,
                filled,
                total,
                score * 100.0,
                missing.join(", ")
            );
            rejected.push(product);
        }
    }

    if !rejected.is_empty() {
        warn!(
            "Rejected {}/{} products below {:.0}% quality threshold",
            rejected.len(),
            passed.len() + rejected.len(),
            threshold * 100.0,
        );
    }

    (passed, rejected)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_motor(name: &str, with_specs: bool) -> Product {
        let json = if with_specs {
            format!(
                r#"{{
                "product_type": "motor",
                "product_name": "{}",
                "rated_speed": "3000;rpm",
                "rated_torque": "2.5;Nm",
                "rated_power": "400;W",
                "rated_current": "2.6;A",
                "poles": 8
            }}"#,
                name
            )
        } else {
            format!(
                r#"{{
                "product_type": "motor",
                "product_name": "{}"
            }}"#,
                name
            )
        };
        serde_json::from_str(&json).unwrap()
    }

    #[test]
    fn test_score_product_full() {
        let product = make_motor("Full", true);
        let (score, filled, total, missing) = score_product(&product);
        assert!(score > 0.2);
        assert!(filled > 0);
        assert!(total > 0);
        assert!(missing.len() < total);
    }

    #[test]
    fn test_score_product_empty() {
        let product = make_motor("Empty", false);
        let (score, _filled, total, missing) = score_product(&product);
        assert!(score < 0.3);
        assert!(!missing.is_empty());
        assert!(total > 0);
    }

    #[test]
    fn test_filter_products_passes_good() {
        let products = vec![make_motor("Good", true)];
        let (passed, rejected) = filter_products(products, Some(0.1));
        assert_eq!(passed.len(), 1);
        assert_eq!(rejected.len(), 0);
    }

    #[test]
    fn test_filter_products_rejects_bad() {
        let products = vec![make_motor("Bad", false)];
        let (passed, rejected) = filter_products(products, Some(0.9));
        assert_eq!(passed.len(), 0);
        assert_eq!(rejected.len(), 1);
    }

    #[test]
    fn test_filter_mixed() {
        let products = vec![make_motor("Good", true), make_motor("Bad", false)];
        // Good motor has 5/22 specs (~23%), bad has 0/22 (0%)
        // Use 0.2 threshold so good passes but bad fails
        let (passed, rejected) = filter_products(products, Some(0.2));
        assert_eq!(passed.len(), 1);
        assert_eq!(rejected.len(), 1);
    }
}
