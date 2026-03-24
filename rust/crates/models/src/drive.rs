//! Drive product model.

use serde::{Deserialize, Serialize};

use crate::common::{MinMaxUnit, ValueUnit};
use crate::product::ProductBase;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DriveType {
    Servo,
    #[serde(rename = "variable frequency")]
    VariableFrequency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Drive {
    #[serde(flatten)]
    pub base: ProductBase,
    #[serde(rename = "type", skip_serializing_if = "Option::is_none")]
    pub drive_type: Option<DriveType>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub series: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_voltage: Option<MinMaxUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_voltage_frequency: Option<Vec<MinMaxUnit>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input_voltage_phases: Option<Vec<i32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rated_current: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub peak_current: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_power: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub switching_frequency: Option<Vec<ValueUnit>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fieldbus: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub encoder_feedback_support: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ethernet_ports: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_inputs: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_outputs: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analog_inputs: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analog_outputs: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub safety_rating: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub approvals: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_humidity: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_rating: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ambient_temp: Option<MinMaxUnit>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_drive_minimal() {
        let json = r#"{"product_name": "ASD-B3"}"#;
        let drive: Drive = serde_json::from_str(json).unwrap();
        assert_eq!(drive.base.product_name, "ASD-B3");
    }

    #[test]
    fn test_drive_with_lists() {
        let json = r#"{
            "product_name": "ASD-B3",
            "fieldbus": ["EtherCAT", "CANopen"],
            "switching_frequency": ["8;kHz", "16;kHz"]
        }"#;
        let drive: Drive = serde_json::from_str(json).unwrap();
        assert_eq!(drive.fieldbus.as_ref().unwrap().len(), 2);
        // kHz is not converted (intentionally excluded)
        assert_eq!(
            drive.switching_frequency.as_ref().unwrap()[0].as_str(),
            Some("8;kHz")
        );
    }
}
