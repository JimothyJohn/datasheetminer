//! Motor product model.

use serde::{Deserialize, Serialize};

use crate::common::{MinMaxUnit, ValueUnit};
use crate::product::ProductBase;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorType {
    #[serde(rename = "brushless dc")]
    BrushlessDc,
    #[serde(rename = "brushed dc")]
    BrushedDc,
    #[serde(rename = "ac induction")]
    AcInduction,
    #[serde(rename = "ac synchronous")]
    AcSynchronous,
    #[serde(rename = "ac servo")]
    AcServo,
    #[serde(rename = "permanent magnet")]
    PermanentMagnet,
    #[serde(rename = "hybrid")]
    Hybrid,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Motor {
    #[serde(flatten)]
    pub base: ProductBase,
    #[serde(rename = "type", skip_serializing_if = "Option::is_none")]
    pub motor_type: Option<MotorType>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub series: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rated_voltage: Option<MinMaxUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rated_speed: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_speed: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rated_torque: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub peak_torque: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rated_power: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub encoder_feedback_support: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub poles: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rated_current: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub peak_current: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub voltage_constant: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub torque_constant: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resistance: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub inductance: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_rating: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rotor_inertia: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub axial_load_force_rating: Option<MinMaxUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub radial_load_force_rating: Option<MinMaxUnit>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_motor_minimal() {
        let json = r#"{"product_name": "Test Motor"}"#;
        let motor: Motor = serde_json::from_str(json).unwrap();
        assert_eq!(motor.base.product_name, "Test Motor");
        assert!(motor.motor_type.is_none());
        assert!(motor.rated_speed.is_none());
    }

    #[test]
    fn test_motor_with_specs() {
        let json = r#"{
            "product_name": "ECMA-C30804",
            "manufacturer": "Delta Electronics",
            "type": "ac servo",
            "rated_speed": "3000;rpm",
            "rated_torque": "2.5;Nm",
            "rated_voltage": "200-240;V",
            "rated_power": "400;W",
            "poles": 8
        }"#;
        let motor: Motor = serde_json::from_str(json).unwrap();
        assert_eq!(
            motor.rated_speed.as_ref().unwrap().as_str(),
            Some("3000;rpm")
        );
        assert_eq!(
            motor.rated_torque.as_ref().unwrap().as_str(),
            Some("2.5;Nm")
        );
        assert_eq!(
            motor.rated_voltage.as_ref().unwrap().as_str(),
            Some("200-240;V")
        );
        assert_eq!(motor.rated_power.as_ref().unwrap().as_str(), Some("400;W"));
        assert_eq!(motor.poles, Some(8));
    }

    #[test]
    fn test_motor_unit_conversion() {
        let json = r#"{"product_name": "T", "rated_torque": "500;mNm", "rated_current": "500;mA"}"#;
        let motor: Motor = serde_json::from_str(json).unwrap();
        assert_eq!(
            motor.rated_torque.as_ref().unwrap().as_str(),
            Some("0.5;Nm")
        );
        assert_eq!(
            motor.rated_current.as_ref().unwrap().as_str(),
            Some("0.5;A")
        );
    }
}
