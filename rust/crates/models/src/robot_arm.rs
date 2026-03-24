//! Robot arm product model with nested component specs.

use serde::{Deserialize, Serialize};

use crate::common::{MinMaxUnit, ValueUnit};
use crate::product::ProductBase;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JointSpecs {
    pub joint_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub working_range: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_speed: Option<ValueUnit>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForceTorqueSensor {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub force_range: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub force_precision: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub torque_range: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub torque_precision: Option<ValueUnit>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolIO {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_in: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_out: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analog_in: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub power_supply_voltage: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub power_supply_current: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub connector_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub communication_protocols: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControllerIO {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_in: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_out: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analog_in: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analog_out: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub quadrature_inputs: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub power_supply: Option<ValueUnit>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Controller {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_rating: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cleanroom_class: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub operating_temp: Option<MinMaxUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub io_ports: Option<ControllerIO>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub communication_protocols: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub power_source: Option<MinMaxUnit>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TeachPendant {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_rating: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display_resolution: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display_size: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub weight: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cable_length: Option<ValueUnit>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RobotArm {
    #[serde(flatten)]
    pub base: ProductBase,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub payload: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reach: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub degrees_of_freedom: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pose_repeatability: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_tcp_speed: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ip_rating: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cleanroom_class: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub noise_level: Option<ValueUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mounting_position: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub operating_temp: Option<MinMaxUnit>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub materials: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub joints: Option<Vec<JointSpecs>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub force_torque_sensor: Option<ForceTorqueSensor>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_io: Option<ToolIO>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub controller: Option<Controller>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub teach_pendant: Option<TeachPendant>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub safety_certifications: Option<Vec<String>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_robot_arm_basic() {
        let json = r#"{
            "product_name": "UR5e",
            "payload": "5;kg",
            "reach": "850;mm",
            "degrees_of_freedom": 6
        }"#;
        let arm: RobotArm = serde_json::from_str(json).unwrap();
        assert_eq!(arm.payload.as_ref().unwrap().as_str(), Some("5;kg"));
        assert_eq!(arm.reach.as_ref().unwrap().as_str(), Some("850;mm"));
        assert_eq!(arm.degrees_of_freedom, Some(6));
    }

    #[test]
    fn test_robot_arm_nested_joints() {
        let json = r#"{
            "product_name": "UR5e",
            "joints": [
                {"joint_name": "Base", "working_range": "360;deg", "max_speed": "180;deg/s"}
            ]
        }"#;
        let arm: RobotArm = serde_json::from_str(json).unwrap();
        let joints = arm.joints.unwrap();
        assert_eq!(joints.len(), 1);
        assert_eq!(joints[0].joint_name, "Base");
    }

    #[test]
    fn test_teach_pendant() {
        let json = r#"{
            "display_size": "12;in",
            "weight": "1.6;kg",
            "cable_length": "4.5;m"
        }"#;
        let tp: TeachPendant = serde_json::from_str(json).unwrap();
        // Length units intentionally not converted
        assert_eq!(tp.display_size.as_ref().unwrap().as_str(), Some("12;in"));
        assert_eq!(tp.cable_length.as_ref().unwrap().as_str(), Some("4.5;m"));
    }
}
