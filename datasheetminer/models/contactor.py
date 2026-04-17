from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import Field

from datasheetminer.models.common import MinMaxUnit, ValueUnit
from datasheetminer.models.product import ProductBase


class Contactor(ProductBase):
    """Electromagnetic contactor (magnetic contactor) or magnetic starter — an
    electromechanical switching device used to control power circuits for
    motors, heaters, lighting, and capacitor loads. Characterized by rated
    operating current at various utilization categories (AC-1/AC-3/AC-4),
    coil voltage ratings, auxiliary contact arrangements, and mechanical
    and electrical durability. Covers AC-operated, DC-operated, mechanically
    latched, reversing, delay-open, and solid-state variants.
    """

    product_type: Literal["contactor"] = "contactor"
    type: Optional[
        Literal[
            "ac operated",
            "dc operated",
            "mechanically latched",
            "reversing",
            "delay open",
            "solid state",
        ]
    ] = None
    series: Optional[str] = None

    # --- General ---
    frame_size: Optional[str] = Field(
        None, description="Frame size designation (e.g. T10, T21, N125, N800)."
    )

    # --- Electrical: main contact ---
    rated_insulation_voltage: Optional[ValueUnit] = Field(
        None, description="Rated insulation voltage of the main contacts."
    )
    rated_impulse_withstand_voltage: Optional[ValueUnit] = Field(
        None, description="Rated impulse withstand voltage (Uimp)."
    )
    rated_frequency: Optional[str] = Field(
        None, description="Rated operating frequency (e.g. '50/60 Hz')."
    )
    pollution_degree: Optional[int] = Field(
        None, description="Pollution degree rating per IEC 60947-1 (e.g. 3)."
    )

    # --- AC-3 ratings (motor duty) ---
    rated_operating_current_ac3_220v: Optional[ValueUnit] = Field(
        None,
        description=(
            "Rated operating current for utilization category AC-3 at 220-240 V "
            "(three-phase squirrel-cage motor, standard duty)."
        ),
    )
    rated_operating_current_ac3_440v: Optional[ValueUnit] = Field(
        None,
        description="Rated operating current for category AC-3 at 380-440 V.",
    )
    rated_operating_current_ac3_500v: Optional[ValueUnit] = Field(
        None, description="Rated operating current for category AC-3 at 500 V."
    )
    rated_operating_current_ac3_690v: Optional[ValueUnit] = Field(
        None, description="Rated operating current for category AC-3 at 690 V."
    )
    rated_capacity_ac3_220v: Optional[ValueUnit] = Field(
        None, description="Rated motor capacity (kW) for AC-3 at 220-240 V."
    )
    rated_capacity_ac3_440v: Optional[ValueUnit] = Field(
        None, description="Rated motor capacity (kW) for AC-3 at 380-440 V."
    )

    # --- AC-1 ratings (resistive / heater duty) ---
    rated_operating_current_ac1: Optional[ValueUnit] = Field(
        None,
        description=(
            "Rated operating current for utilization category AC-1 "
            "(resistive/heater load) at 100-240 V."
        ),
    )
    conventional_free_air_thermal_current: Optional[ValueUnit] = Field(
        None,
        description=(
            "Conventional free-air thermal current Ith — the continuous current "
            "the main contacts can carry without exceeding rated temperature rise."
        ),
    )

    # --- Coil ---
    coil_voltage_designations: Optional[List[str]] = Field(
        None,
        description=(
            "Available coil voltage designations (e.g. 'AC24V', 'AC200V', 'DC24V')."
        ),
    )
    coil_power_consumption_sealed: Optional[ValueUnit] = Field(
        None,
        description="Coil power consumption in the sealed (energized, steady-state) state.",
    )
    coil_consumption_inrush: Optional[ValueUnit] = Field(
        None,
        description=(
            "Coil inrush power consumption at initial energization (VA for AC coils)."
        ),
    )

    # --- Mechanical ---
    number_of_poles: Optional[int] = Field(
        None, description="Number of main circuit poles (typically 3)."
    )
    auxiliary_contact_arrangement: Optional[str] = Field(
        None,
        description="Standard auxiliary contact arrangement (e.g. '1a', '1a1b', '2a2b').",
    )
    mechanical_durability: Optional[ValueUnit] = Field(
        None,
        description=(
            "Mechanical durability — number of no-load switching operations "
            "before wear-out."
        ),
    )
    electrical_durability_ac3: Optional[ValueUnit] = Field(
        None,
        description="Electrical durability for AC-3 duty — number of switching operations.",
    )
    switching_frequency_ac3: Optional[str] = Field(
        None,
        description="Maximum switching frequency for AC-3 duty (e.g. '1800 times/hour').",
    )

    # --- Performance ---
    making_capacity: Optional[ValueUnit] = Field(
        None, description="Making (closing) current capacity at rated voltage."
    )
    breaking_capacity: Optional[ValueUnit] = Field(
        None, description="Breaking (opening) current capacity at rated voltage."
    )
    operating_time_close: Optional[str] = Field(
        None,
        description="Operating time from coil ON to main contact ON (e.g. '12-18 ms').",
    )
    operating_time_open: Optional[str] = Field(
        None,
        description="Operating time from coil OFF to main contact OFF (e.g. '5-20 ms').",
    )
    iec_rail_mounting: Optional[bool] = Field(
        None, description="Whether the contactor supports IEC 35 mm DIN rail mounting."
    )

    # --- Environmental ---
    ip_rating: Optional[int] = Field(
        None, description="IP (Ingress Protection) rating if specified."
    )
    operating_temp: Optional[MinMaxUnit] = Field(
        None, description="Operating ambient temperature range."
    )

    # --- Certifications ---
    approvals: Optional[List[str]] = Field(
        None,
        description="Standards and certifications (e.g. 'JIS C8201-4-1', 'IEC60947-4-1', 'UL', 'CCC', 'CE').",
    )
