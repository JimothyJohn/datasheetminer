"""Integration-point layer: how products plug into each other.

Separates *what a product is* (datasheetminer.models) from *how it
connects to another product* (this package). Each product exposes a set
of named ports; compatibility is checked by comparing ports of matching
shape — e.g. a drive's motor-output port against a motor's power-input
port.

Three files, one responsibility each:

    ports.py    — port schemas (ElectricalPowerPort, MechanicalShaftPort,
                  FeedbackPort, FieldbusPort, CoilPort)
    adapters.py — map a product model to its named ports
    compat.py   — pairwise compatibility checks between products
"""

from datasheetminer.integration.adapters import ports_for
from datasheetminer.integration.compat import (
    CompatibilityReport,
    CompatResult,
    check,
)
from datasheetminer.integration.ports import (
    CoilPort,
    ElectricalPowerPort,
    FeedbackPort,
    FieldbusPort,
    MechanicalShaftPort,
    Port,
)

__all__ = [
    "CompatResult",
    "CompatibilityReport",
    "CoilPort",
    "ElectricalPowerPort",
    "FeedbackPort",
    "FieldbusPort",
    "MechanicalShaftPort",
    "Port",
    "check",
    "ports_for",
]
