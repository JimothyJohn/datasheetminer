"""Electromagnetic contactor Pydantic model.

Schema grounded in IEC 60947-4-1 / UL 508 vocabulary common to ABB AF
series, Schneider TeSys D, Siemens SIRIUS 3RT, Allen-Bradley 100-C, Fuji
SC, and Mitsubishi MS-T/N. See contactor.md in this directory for
sources and field-by-field reasoning.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from datasheetminer.models.common import MinMaxUnit, ValueUnit
from datasheetminer.models.product import ProductBase


class ContactorPowerRating(BaseModel):
    """A single row from a contactor's utilization-category rating table.

    Contactor datasheets publish AC-3 / AC-1 / AC-4 ratings as multi-row
    tables keyed by voltage (e.g. 220V / 400V / 500V / 690V). This type
    captures one row; ``Contactor.ratings_ac3`` holds the full table.
    Power is reported in both kW (IEC) and hp (UL/NEMA); we store both
    because every vendor publishes both and which one the user filters
    on depends on the market.
    """

    voltage: Optional[ValueUnit] = Field(
        None, description="Operational voltage for this rating row (e.g. 400 V)."
    )
    voltage_group: Optional[str] = Field(
        None,
        description=(
            "Vendor voltage-bin label when the row represents a range "
            "(e.g. '380-415', '220-240', '500-525')."
        ),
    )
    current: Optional[ValueUnit] = Field(
        None, description="Rated operational current Ie at this voltage (A)."
    )
    power_kw: Optional[ValueUnit] = Field(
        None, description="Motor power rating at this voltage (kW, IEC)."
    )
    power_hp: Optional[ValueUnit] = Field(
        None,
        description=(
            "Motor power rating at this voltage (hp, UL/NEMA market). "
            "Store as float; fractional hp like '7-1/2 hp' → 7.5."
        ),
    )
    ambient_temp: Optional[ValueUnit] = Field(
        None,
        description=(
            "Ambient temperature the row applies to (°C). AC-1 tables on "
            "ABB and Rockwell publish different Ie at 40/60/70 °C."
        ),
    )


class ContactorIcwRating(BaseModel):
    """Short-time withstand current at a specific duration.

    ABB and Allen-Bradley publish Icw as a curve (1 s / 10 s / 30 s / 1 min
    / 10 min); a scalar Icw loses that shape. Distinct from SCCR (UL
    short-circuit current rating), which is a single value.
    """

    duration: ValueUnit = Field(..., description="Withstand duration, e.g. 10 s.")
    current: ValueUnit = Field(
        ..., description="Withstand current for the duration (A)."
    )


class Contactor(ProductBase):
    """Electromagnetic contactor (magnetic contactor) or solid-state
    contactor — an electromechanical or semiconductor switching device
    used to control power circuits for motors, heaters, lighting, and
    capacitor loads. Modelled after the IEC 60947-4-1 utilization
    categories (AC-1 through AC-4, DC-1, DC-13) with parallel UL 508
    fields (hp ratings, SCCR) for the North-American market.

    Covers AC-operated, DC-operated, mechanically-latched, reversing,
    delay-open, and solid-state variants.
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
            "vacuum",
            "definite purpose",
        ]
    ] = None
    series: Optional[str] = None

    # --- Vendor frame designations ---
    vendor_frame_size: Optional[str] = Field(
        None,
        description=(
            "Vendor-specific frame/size code as printed on the datasheet "
            "(e.g. ABB 'AF09', Siemens 'S00', Fuji 'SC-N1', Mitsubishi "
            "'T10'). Not portable across vendors; kept only for cross-"
            "referencing a specific datasheet."
        ),
    )
    nema_size: Optional[str] = Field(
        None,
        description=(
            "NEMA size designation ('00', '0', '1', ..., '9'). Only US-"
            "market datasheets (ABB North America, Allen-Bradley) "
            "publish this."
        ),
    )

    # --- Insulation & voltage ---
    rated_insulation_voltage: Optional[ValueUnit] = Field(
        None,
        description="Rated insulation voltage Ui (V). Typically 690 V IEC / 600 V UL.",
    )
    rated_impulse_withstand_voltage: Optional[ValueUnit] = Field(
        None, description="Rated impulse withstand voltage Uimp (kV). Typically 6 kV."
    )
    rated_operational_voltage_max: Optional[ValueUnit] = Field(
        None,
        description=(
            "Maximum rated operational voltage Ue (V). Distinct from Ui; "
            "defines the upper bound of the utilization-category ratings."
        ),
    )
    rated_frequency: Optional[str] = Field(
        None, description="Line frequency of the main circuit (e.g. '50/60 Hz')."
    )
    pollution_degree: Optional[int] = Field(
        None, description="Pollution degree per IEC 60947-1 (typically 3)."
    )

    # --- Headline AC-3 ratings (IEC: 400 V, NEMA: 480 V) ---
    # These are the single-scalar numbers that vendors lead with in the
    # product name and that users sort the catalog by. The full tables
    # live in ratings_ac3 / ratings_ac1 below.
    ie_ac3_400v: Optional[ValueUnit] = Field(
        None,
        description=(
            "Rated operational current at AC-3, Ue = 400 V (A). IEC "
            "headline figure — use this for filtering / comparing."
        ),
    )
    motor_power_ac3_400v_kw: Optional[ValueUnit] = Field(
        None,
        description=(
            "Rated motor power at AC-3, Ue = 400 V (kW). Appears in the "
            "product name on most Siemens/Schneider SKUs."
        ),
    )
    motor_power_ac3_480v_hp: Optional[ValueUnit] = Field(
        None,
        description=(
            "Rated motor power at AC-3, Ue = 480 V (hp). NEMA/UL headline "
            "figure for the US market."
        ),
    )

    # --- Full utilization-category rating tables ---
    ratings_ac3: Optional[List[ContactorPowerRating]] = Field(
        None,
        description=(
            "Per-voltage AC-3 rating table (squirrel-cage motor, starting). "
            "Captures the full voltage/current/power matrix the datasheet "
            "publishes."
        ),
    )
    ratings_ac1: Optional[List[ContactorPowerRating]] = Field(
        None,
        description=(
            "Per-voltage AC-1 rating table (non-inductive or resistive "
            "heating loads). Rows may also differ by ambient temperature."
        ),
    )
    ratings_ac4: Optional[List[ContactorPowerRating]] = Field(
        None,
        description=(
            "Per-voltage AC-4 rating table (inching/plugging duty). Many "
            "vendors publish only life curves for AC-4 and omit the table."
        ),
    )

    # --- Thermal / short-circuit ---
    conventional_thermal_current: Optional[ValueUnit] = Field(
        None,
        description=(
            "Conventional free-air thermal current Ith (A) — continuous "
            "current the main contacts carry without exceeding rated "
            "temperature rise."
        ),
    )
    short_circuit_withstand_icw: Optional[List[ContactorIcwRating]] = Field(
        None,
        description=(
            "Short-time withstand current curve (duration/current pairs). "
            "ABB/Allen-Bradley publish 4+ points; capture the full curve."
        ),
    )
    sccr: Optional[ValueUnit] = Field(
        None,
        description=(
            "UL short-circuit current rating (kA). North-American metric "
            "distinct from Icw; single scalar."
        ),
    )

    # --- Coil (control circuit) ---
    coil_voltage_range_ac: Optional[MinMaxUnit] = Field(
        None,
        description=(
            "AC coil voltage range offered across the SKU family "
            "(e.g. 24–500 V AC). Individual SKUs will have a single Uc."
        ),
    )
    coil_voltage_range_dc: Optional[MinMaxUnit] = Field(
        None, description="DC coil voltage range offered across the SKU family (V)."
    )
    coil_voltage_options: Optional[List[str]] = Field(
        None,
        description=(
            "Explicit coil voltage designations offered (e.g. '24V AC', "
            "'230V AC', '24V DC'). Populated when the datasheet lists "
            "discrete options rather than a continuous range."
        ),
    )
    coil_pickup_factor: Optional[MinMaxUnit] = Field(
        None,
        description=(
            "Operating range for reliable pickup as a fraction of Uc "
            "(e.g. 0.85–1.1 ×Uc). Unitless ratio — use unit='×Uc'."
        ),
    )
    coil_dropout_factor: Optional[MinMaxUnit] = Field(
        None,
        description=(
            "Drop-out voltage as a fraction of Uc (e.g. 0.2–0.75 ×Uc). Unitless ratio."
        ),
    )
    coil_time_constant: Optional[ValueUnit] = Field(
        None,
        description=(
            "DC coil time constant (ms). Schneider TeSys D publishes this "
            "for DC coils; rarely meaningful for AC."
        ),
    )
    coil_power_consumption_sealed: Optional[ValueUnit] = Field(
        None,
        description=(
            "Sealed (energized steady-state) coil consumption. W for DC, VA for AC."
        ),
    )
    coil_power_consumption_inrush: Optional[ValueUnit] = Field(
        None,
        description="Inrush coil consumption at pickup. VA for AC, W for DC.",
    )

    # --- Contacts ---
    number_of_poles: Optional[int] = Field(
        None, description="Number of main-circuit poles (typically 3 or 4)."
    )
    auxiliary_contact_configuration: Optional[str] = Field(
        None,
        description=(
            "Aux contact arrangement, e.g. '1NO', '1NO+1NC', '2a2b'. "
            "Vendor notation varies; store as printed."
        ),
    )

    # --- Durability / switching performance ---
    mechanical_durability: Optional[ValueUnit] = Field(
        None,
        description="Mechanical endurance (operations) without load.",
    )
    electrical_durability_ac3: Optional[ValueUnit] = Field(
        None, description="Electrical endurance under AC-3 duty (operations)."
    )
    operating_frequency_ac3: Optional[ValueUnit] = Field(
        None, description="Maximum switching frequency under AC-3 (operations/hour)."
    )
    making_capacity: Optional[ValueUnit] = Field(
        None, description="Making (closing) current capacity at rated voltage (A)."
    )
    breaking_capacity: Optional[ValueUnit] = Field(
        None, description="Breaking (opening) current capacity at rated voltage (A)."
    )
    operating_time_close: Optional[MinMaxUnit] = Field(
        None, description="Close operate time from coil-on to main-contact-on (ms)."
    )
    operating_time_open: Optional[MinMaxUnit] = Field(
        None, description="Open operate time from coil-off to main-contact-off (ms)."
    )

    # --- Environmental ---
    operating_temp: Optional[MinMaxUnit] = Field(
        None, description="Operating ambient temperature range (°C)."
    )
    storage_temp: Optional[MinMaxUnit] = Field(
        None, description="Storage temperature range (°C)."
    )
    ip_rating: Optional[int] = Field(
        None, description="IP protection rating (typically 20 for front of panel)."
    )
    altitude_max: Optional[ValueUnit] = Field(
        None, description="Maximum operating altitude without derating (m)."
    )

    # --- Standards / certifications ---
    standards_compliance: Optional[List[str]] = Field(
        None,
        description=(
            "Formal standards the device claims compliance with — "
            "IEC 60947-4-1, UL 508, CSA 22.2 No. 14, GB 14048.4, "
            "EN 60947-4-1. Separate from marketing certifications."
        ),
    )
    certifications: Optional[List[str]] = Field(
        None,
        description=(
            "Marks and third-party certifications: CE, CCC, cULus, "
            "UL Listed, BV, DNV, GL, EAC. Separate from standards."
        ),
    )
    mounting_types: Optional[List[str]] = Field(
        None,
        description=(
            "Supported mounting styles, e.g. ['din_rail_35mm', 'panel_screw']."
        ),
    )
