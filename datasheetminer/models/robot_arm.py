# robot_arm.py
# AI-generated comment:
# This module defines the Pydantic models for a collaborative robot arm.
# It builds on ProductBase and includes nested models for complex components
# like joints, I/O, and controllers, based on the Universal Robots e-Series.

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from datasheetminer.models.common import MinMaxUnit, ValueUnit
from datasheetminer.models.product import ProductBase


class JointSpecs(BaseModel):
    """Defines the specifications for a single robot joint."""

    joint_name: str = Field(
        ..., description="Name of the joint (e.g., 'Base', 'Wrist 1')"
    )
    working_range: Optional[ValueUnit] = Field(
        None, description="The rotational range of the joint"
    )
    max_speed: Optional[ValueUnit] = Field(
        None, description="Maximum speed of the joint"
    )


class ForceTorqueSensor(BaseModel):
    """Defines the specifications of the built-in force/torque sensor."""

    force_range: Optional[ValueUnit] = Field(
        None, description="Measurement range for force (e.g., in N)"
    )
    force_precision: Optional[ValueUnit] = Field(
        None, description="Precision (repeatability) of force measurement (e.g., in N)"
    )
    torque_range: Optional[ValueUnit] = Field(
        None, description="Measurement range for torque (e.g., in Nm)"
    )
    torque_precision: Optional[ValueUnit] = Field(
        None,
        description="Precision (repeatability) of torque measurement (e.g., in Nm)",
    )


class ToolIO(BaseModel):
    """Defines the I/O ports available at the tool (end-effector) flange."""

    digital_in: int = Field(None, description="Number of digital inputs")  #
    digital_out: int = Field(None, description="Number of digital outputs")  #
    analog_in: int = Field(None, description="Number of analog inputs")  #
    power_supply_voltage: Optional[ValueUnit] = Field(
        None,  #
        description="Selectable power supply voltage (e.g., 12V or 24V)",
    )
    power_supply_current: Optional[ValueUnit] = Field(
        None, description="Maximum current for the tool power supply (e.g., in mA or A)"
    )
    connector_type: Optional[str] = Field(
        "M8 8-pin",
        description="Physical connector type at the tool",  #
    )
    communication_protocols: Optional[List[str]] = Field(
        ["Modbus TCP", "PROFINET", "Ethernet/IP"],  #
    )


class ControllerIO(BaseModel):
    """Defines the I/O ports available in the main control box."""

    digital_in: int = Field(16, description="Number of digital inputs")  #
    digital_out: int = Field(16, description="Number of digital outputs")  #
    analog_in: int = Field(2, description="Number of analog inputs")  #
    analog_out: int = Field(2, description="Number of analog outputs")  #
    quadrature_inputs: int = Field(
        4, description="Number of quadrature digital inputs"
    )  #
    power_supply: Optional[ValueUnit] = Field(
        "2;A",
        description="I/O power supply current at 24V",  #
    )


class Controller(BaseModel):
    """Defines the specifications for the robot's control box."""

    ip_rating: Optional[str] = Field(
        "IP44", description="IP rating of the control box"
    )  #
    cleanroom_class: Optional[str] = Field(
        "ISO Class 6",
        description="Cleanroom classification (ISO 14644-1)",  #
    )
    operating_temp: Optional[MinMaxUnit] = Field(
        "0-50;°C",  #
        description="Operating temperature range for the controller",
    )
    io_ports: Optional[ControllerIO] = Field(
        default=None,
        description="I/O ports on the controller",
    )
    communication_protocols: Optional[List[str]] = Field(
        ["Modbus TCP", "PROFINET", "Ethernet/IP"],  #
        description="List of supported communication protocols",
    )
    power_source: Optional[MinMaxUnit] = Field(
        ";VAC",
        description="Main power source requirements (e.g., 100-240VAC)",  #
    )


class TeachPendant(BaseModel):
    """Defines the specifications for the teach pendant."""

    ip_rating: Optional[str] = Field(
        "IP54", description="IP rating of the teach pendant"
    )  #
    display_resolution: Optional[str] = Field(
        "1280 x 800",
        description="Screen resolution in pixels",  #
    )
    display_size: Optional[ValueUnit] = Field(
        "12;in",
        description="Diagonal screen size",  #
    )
    weight: Optional[ValueUnit] = Field(
        "1.6;kg",
        description="Weight of the pendant",  #
    )
    cable_length: Optional[ValueUnit] = Field(
        "4.5;m",
        description="Cable length",  #
    )


class RobotArm(ProductBase):
    """
    A Pydantic model representing a collaborative robot arm.

    This model extends ProductBase to include detailed specifications
    for the arm, controller, and teach pendant. Defaults are based
    on the Universal Robots e-Series.
    """

    # --- Product Identification ---
    product_type: str = Field("robot_arm", description="Type of product")
    manufacturer: str = Field("Universal Robots", description="Manufacturer name")  #
    product_family: str = Field("e-Series", description="Product family or series")  #

    # --- Core Performance ---
    payload: Optional[ValueUnit] = Field(
        None, description="Rated payload capacity (e.g., in kg)"
    )
    reach: Optional[ValueUnit] = Field(
        None, description="Maximum reach from center of base (e.g., in mm)"
    )
    degrees_of_freedom: int = Field(6, description="Number of rotating joints")  #
    pose_repeatability: Optional[ValueUnit] = Field(
        None, description="Pose repeatability per ISO 9283 (e.g., in mm)"
    )
    max_tcp_speed: Optional[ValueUnit] = Field(
        None, description="Maximum speed of the Tool Center Point (e.g., in m/s)"
    )

    # --- Arm Specifications ---
    ip_rating: Optional[str] = Field(
        "IP54",
        description="IP rating of the robot arm",  #
    )
    cleanroom_class: Optional[str] = Field(
        "ISO Class 5",
        description="Cleanroom classification (ISO 14644-1)",  #
    )
    noise_level: Optional[ValueUnit] = Field(
        None,
        description="Typical noise level (e.g., in dB(A))",  #
    )
    mounting_position: Optional[str] = Field(
        "Any Orientation",
        description="Allowed mounting positions",  #
    )
    operating_temp: Optional[MinMaxUnit] = Field(
        "0-50;°C",  #
        description="Operating temperature range for the arm",
    )
    materials: Optional[List[str]] = Field(
        ["Aluminium", "Plastic", "Steel"],  #
        description="Main materials used in arm construction",
    )

    # --- Nested Components ---
    joints: Optional[List[JointSpecs]] = Field(
        None, description="List of specifications for each joint"
    )
    force_torque_sensor: Optional[ForceTorqueSensor] = Field(
        default=None,
        description="Specifications of the integrated F/T sensor",  #
    )
    tool_io: Optional[ToolIO] = Field(
        default=None, description="I/O and power at the tool flange"
    )
    controller: Optional[Controller] = Field(
        default=None,
        description="Specifications of the control box",
    )
    teach_pendant: Optional[TeachPendant] = Field(
        default=None,
        description="Specifications of the teach pendant",
    )

    # --- Certifications ---
    safety_certifications: Optional[List[str]] = Field(
        ["EN ISO 13849-1, PLd Category 3", "EN ISO 10218-1"],  #
        description="List of safety certifications",
    )
