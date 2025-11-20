# gearhead.py
# AI-generated comment:
# This module defines the Pydantic model for a gearhead, a mechanical device
# used to increase torque and reduce speed from a motor. It builds upon the
# ProductBase model to include specific technical attributes relevant to
# gearheads, such as gear ratio, torque ratings, and backlash. This structured
# approach ensures data consistency for gearhead products.

from __future__ import annotations

from typing import Optional

from pydantic import Field

from datasheetminer.models.common import MinMaxUnit, ValueUnit
from datasheetminer.models.product import ProductBase


class Gearhead(ProductBase):
    """
    A Pydantic model representing a gearhead.

    This model extends the ProductBase to include attributes specific to
    gearheads, which are crucial for engineering and selection processes.
    This model is pre-populated with defaults for the Sesame PHL series.
    """

    # --- Performance Specifications ---
    gear_ratio: Optional[float] = Field(
        None,
        description="The ratio of input speed to output speed (e.g., 10.0 for 10:1)",
    )
    gear_type: Optional[str] = Field(
        "helical planetary",
        description="Type of gear mechanism (e.g., 'Planetary', 'Spur', 'Helical')",
    )
    stages: Optional[int] = Field(
        None, description="Number of gear stages (e.g., 1 or 2)"
    )
    nominal_input_speed: Optional[ValueUnit] = Field(
        None, description="Nominal continuous input speed (e.g., in rpm)"
    )
    max_input_speed: Optional[ValueUnit] = Field(
        None, description="Maximum allowable input speed (e.g., in rpm)"
    )
    max_continuous_torque: Optional[ValueUnit] = Field(
        None, description="Nominal output torque (T2N) (e.g., in Nm)"
    )
    max_peak_torque: Optional[ValueUnit] = Field(
        None, description="Emergency stop torque (T2NOT) (e.g., in Nm)"
    )
    backlash: Optional[ValueUnit] = Field(
        None, description="Rotational lost motion (e.g., in arcminutes)"
    )
    efficiency: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Efficiency of the gearhead as a ratio (e.g., 0.97 for 97%)",
    )
    torsional_rigidity: Optional[ValueUnit] = Field(
        None, description="Torsional rigidity (e.g., in Nm/arcmin)"
    )
    rotor_inertia: Optional[ValueUnit] = Field(
        None, description="Moment of inertia for the gearbox (e.g., in kg.cm²)"
    )
    noise_level: Optional[ValueUnit] = Field(
        None, description="Noise level at 1m distance (e.g., in dBA)"
    )

    # --- Mechanical Specifications ---
    frame_size: Optional[str] = Field(
        None, description="Gearbox frame size, corresponding to flange (e.g., 42, 60)"
    )
    input_shaft_diameter: Optional[ValueUnit] = Field(
        None, description="Diameter of the input shaft (motor specific) (e.g., in mm)"
    )
    output_shaft_diameter: Optional[ValueUnit] = Field(
        None, description="Diameter of the output shaft (e.g., in mm)"
    )
    max_radial_load: Optional[ValueUnit] = Field(
        None, description="Maximum radial load (F2m) (e.g., in N)"
    )
    max_axial_load: Optional[ValueUnit] = Field(
        None, description="Maximum axial load (F2ab) (e.g., in N)"
    )

    # --- Environmental & Service ---
    ip_rating: Optional[str] = Field(None, description="Ingress Protection (IP) rating")
    operating_temp: Optional[MinMaxUnit] = Field(
        None,
        description="Operating temperature range",
    )
    service_life: Optional[ValueUnit] = Field(
        None, description="Expected service life (e.g., in hours)"
    )
    lubrication_type: Optional[str] = Field(
        "Synthetic Lubricant", description="Type of lubrication used"
    )
