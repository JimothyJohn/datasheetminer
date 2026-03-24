//! Gearhead product model.

use serde::{Deserialize, Serialize};

use crate::common::{MinMaxUnit, ValueUnit};
use crate::product::ProductBase;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Gearhead {
    #[serde(flatten)]
    pub base: ProductBase,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gear_ratio: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gear_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stages: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub nominal_input_speed: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_input_speed: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_continuous_torque: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_peak_torque: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub backlash: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub efficiency: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub torsional_rigidity: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rotor_inertia: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub noise_level: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frame_size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_shaft_diameter: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_shaft_diameter: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_radial_load: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_axial_load: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_rating: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub operating_temp: Option<MinMaxUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub service_life: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lubrication_type: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gearhead_basic() {
        let json = r#"{
            "product_name": "PHL-060",
            "gear_ratio": 10.0,
            "stages": 1,
            "efficiency": 0.97
        }"#;
        let gh: Gearhead = serde_json::from_str(json).unwrap();
        assert_eq!(gh.gear_ratio, Some(10.0));
        assert_eq!(gh.stages, Some(1));
        assert_eq!(gh.efficiency, Some(0.97));
    }

    #[test]
    fn test_gearhead_force_conversion() {
        let json = r#"{"product_name": "T", "max_radial_load": "5;kN"}"#;
        let gh: Gearhead = serde_json::from_str(json).unwrap();
        assert_eq!(
            gh.max_radial_load.as_ref().unwrap().as_str(),
            Some("5000;N")
        );
    }
}
