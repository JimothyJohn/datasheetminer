"""Tests for unit normalization module."""

import pytest

from datasheetminer.units import normalize_unit, normalize_value_unit


@pytest.mark.unit
class TestNormalizeUnit:
    """Test the low-level normalize_unit function."""

    # --- Torque ---
    def test_mNm_to_Nm(self):
        val, unit = normalize_unit("500", "mNm")
        assert val == "0.5"
        assert unit == "Nm"

    def test_oz_in_to_Nm(self):
        val, unit = normalize_unit("100", "oz-in")
        assert unit == "Nm"
        assert float(val) == pytest.approx(0.706155, rel=1e-3)

    def test_lb_ft_to_Nm(self):
        val, unit = normalize_unit("1", "lb-ft")
        assert unit == "Nm"
        assert float(val) == pytest.approx(1.35582, rel=1e-3)

    def test_kgf_cm_to_Nm(self):
        val, unit = normalize_unit("10", "kgf·cm")
        assert unit == "Nm"
        assert float(val) == pytest.approx(0.980665, rel=1e-3)

    def test_kNm_to_Nm(self):
        val, unit = normalize_unit("2", "kNm")
        assert val == "2000"
        assert unit == "Nm"

    # --- Power ---
    def test_mW_to_W(self):
        val, unit = normalize_unit("500", "mW")
        assert val == "0.5"
        assert unit == "W"

    def test_kW_to_W(self):
        val, unit = normalize_unit("1.5", "kW")
        assert val == "1500"
        assert unit == "W"

    def test_hp_to_W(self):
        val, unit = normalize_unit("1", "hp")
        assert unit == "W"
        assert float(val) == pytest.approx(745.7, rel=1e-3)

    # --- Current ---
    def test_mA_to_A(self):
        val, unit = normalize_unit("500", "mA")
        assert val == "0.5"
        assert unit == "A"

    def test_uA_to_A(self):
        val, unit = normalize_unit("100", "uA")
        assert unit == "A"
        assert float(val) == pytest.approx(0.0001, rel=1e-3)

    # --- Force ---
    def test_kN_to_N(self):
        val, unit = normalize_unit("5", "kN")
        assert val == "5000"
        assert unit == "N"

    def test_lbf_to_N(self):
        val, unit = normalize_unit("10", "lbf")
        assert unit == "N"
        assert float(val) == pytest.approx(44.482, rel=1e-3)

    def test_kgf_to_N(self):
        val, unit = normalize_unit("1", "kgf")
        assert unit == "N"
        assert float(val) == pytest.approx(9.80665, rel=1e-4)

    # --- Speed ---
    def test_rad_s_to_rpm(self):
        val, unit = normalize_unit("314.159", "rad/s")
        assert unit == "rpm"
        assert float(val) == pytest.approx(3000, rel=1e-2)

    def test_rps_to_rpm(self):
        val, unit = normalize_unit("50", "rps")
        assert val == "3000"
        assert unit == "rpm"

    # --- Inertia ---
    def test_gcm2_to_kgcm2(self):
        val, unit = normalize_unit("500", "g·cm²")
        assert val == "0.5"
        assert unit == "kg·cm²"

    def test_kgm2_to_kgcm2(self):
        val, unit = normalize_unit("0.001", "kg·m²")
        assert val == "10"
        assert unit == "kg·cm²"

    def test_oz_in2_to_kgcm2(self):
        val, unit = normalize_unit("10", "oz-in²")
        assert unit == "kg·cm²"
        assert float(val) == pytest.approx(0.720078, rel=1e-3)

    # --- Inductance ---
    def test_H_to_mH(self):
        val, unit = normalize_unit("0.5", "H")
        assert val == "500"
        assert unit == "mH"

    def test_uH_to_mH(self):
        val, unit = normalize_unit("100", "uH")
        assert val == "0.1"
        assert unit == "mH"

    # --- Resistance ---
    def test_ohm_text_to_symbol(self):
        val, unit = normalize_unit("10", "ohm")
        assert val == "10"
        assert unit == "Ω"

    def test_ohms_text_to_symbol(self):
        val, unit = normalize_unit("4.7", "Ohms")
        assert val == "4.7"
        assert unit == "Ω"

    def test_mOhm_to_Ohm(self):
        val, unit = normalize_unit("500", "mΩ")
        assert val == "0.5"
        assert unit == "Ω"

    def test_kOhm_to_Ohm(self):
        val, unit = normalize_unit("10", "kΩ")
        assert val == "10000"
        assert unit == "Ω"

    # --- Temperature ---
    def test_fahrenheit_to_celsius(self):
        val, unit = normalize_unit("212", "°F")
        assert val == "100"
        assert unit == "°C"

    def test_fahrenheit_negative(self):
        val, unit = normalize_unit("-40", "°F")
        assert val == "-40"
        assert unit == "°C"

    # --- Passthrough ---
    def test_canonical_unit_passes_through(self):
        val, unit = normalize_unit("3000", "rpm")
        assert val == "3000"
        assert unit == "rpm"

    def test_unknown_unit_passes_through(self):
        val, unit = normalize_unit("100", "widgets")
        assert val == "100"
        assert unit == "widgets"

    def test_non_numeric_value_passes_through(self):
        val, unit = normalize_unit("2+", "mNm")
        assert val == "2+"
        assert unit == "mNm"

    def test_length_units_not_converted(self):
        """Length units are intentionally excluded from conversion."""
        val, unit = normalize_unit("4.5", "m")
        assert val == "4.5"
        assert unit == "m"

    def test_inches_not_converted(self):
        val, unit = normalize_unit("12", "in")
        assert val == "12"
        assert unit == "in"

    def test_kHz_not_converted(self):
        """Frequency units are intentionally excluded from conversion."""
        val, unit = normalize_unit("8", "kHz")
        assert val == "8"
        assert unit == "kHz"


@pytest.mark.unit
class TestNormalizeValueUnit:
    """Test the compact string normalizer."""

    def test_single_value(self):
        assert normalize_value_unit("500;mNm") == "0.5;Nm"

    def test_range_value(self):
        result = normalize_value_unit("100-500;mA")
        assert result == "0.1-0.5;A"

    def test_canonical_passthrough(self):
        assert normalize_value_unit("3000;rpm") == "3000;rpm"

    def test_unknown_unit_passthrough(self):
        assert normalize_value_unit("200-240;V") == "200-240;V"

    def test_no_semicolon_passthrough(self):
        assert normalize_value_unit("hello") == "hello"

    def test_negative_range(self):
        result = normalize_value_unit("-40-212;°F")
        assert result.endswith(";°C")
        # -40°F = -40°C, 212°F = 100°C
        value_part = result.split(";")[0]
        # Parse with regex since split("-") is ambiguous with negatives
        import re

        m = re.match(r"^(-?[\d.]+)-(-?[\d.]+)$", value_part)
        assert m is not None
        assert float(m.group(1)) == pytest.approx(-40, abs=1)
        assert float(m.group(2)) == pytest.approx(100, abs=1)

    def test_vac_not_converted(self):
        """VAC is not in conversion map, should pass through."""
        assert normalize_value_unit("100-240;VAC") == "100-240;VAC"

    def test_degrees_not_converted(self):
        assert normalize_value_unit("360;deg") == "360;deg"


@pytest.mark.unit
class TestPydanticIntegration:
    """Test that unit conversion works through the Pydantic model layer."""

    def test_motor_torque_mNm_normalized(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", rated_torque="500;mNm")
        assert motor.rated_torque == "0.5;Nm"

    def test_motor_torque_Nm_unchanged(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", rated_torque="2.5;Nm")
        assert motor.rated_torque == "2.5;Nm"

    def test_motor_power_kW_normalized(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", rated_power="1.5;kW")
        assert motor.rated_power == "1500;W"

    def test_motor_current_mA_normalized(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", rated_current="500;mA")
        assert motor.rated_current == "0.5;A"

    def test_motor_resistance_ohm_normalized(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", resistance="4.7;ohm")
        assert motor.resistance == "4.7;Ω"

    def test_motor_inductance_uH_normalized(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", inductance="100;uH")
        assert motor.inductance == "0.1;mH"

    def test_motor_inertia_gcm2_normalized(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(
            product_name="Test", manufacturer="Test", rotor_inertia="500;g·cm²"
        )
        assert motor.rotor_inertia == "0.5;kg·cm²"

    def test_drive_current_mA_normalized(self):
        from datasheetminer.models.drive import Drive

        drive = Drive(product_name="Test", manufacturer="Test", rated_current="500;mA")
        assert drive.rated_current == "0.5;A"

    def test_drive_power_kW_normalized(self):
        from datasheetminer.models.drive import Drive

        drive = Drive(product_name="Test", manufacturer="Test", rated_power="2;kW")
        assert drive.rated_power == "2000;W"

    def test_gearhead_torque_oz_in_normalized(self):
        from datasheetminer.models.gearhead import Gearhead

        gh = Gearhead(
            product_name="Test",
            manufacturer="Test",
            product_type="gearhead",
            rated_torque="100;oz-in",
        )
        parts = gh.rated_torque.split(";")
        assert parts[1] == "Nm"
        assert float(parts[0]) == pytest.approx(0.706155, rel=1e-3)

    def test_gearhead_force_kN_normalized(self):
        from datasheetminer.models.gearhead import Gearhead

        gh = Gearhead(
            product_name="Test",
            manufacturer="Test",
            product_type="gearhead",
            max_radial_load="5;kN",
        )
        assert gh.max_radial_load == "5000;N"

    def test_dict_input_with_conversion(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(
            product_name="Test",
            manufacturer="Test",
            rated_torque={"value": "500", "unit": "mNm"},
        )
        assert motor.rated_torque == "0.5;Nm"

    def test_space_separated_input_with_conversion(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test", rated_torque="500 mNm")
        assert motor.rated_torque == "0.5;Nm"

    def test_none_still_works(self):
        from datasheetminer.models.motor import Motor

        motor = Motor(product_name="Test", manufacturer="Test")
        assert motor.rated_torque is None

    def test_non_numeric_value_preserved(self):
        """Non-convertible units pass through unchanged."""
        from datasheetminer.models.motor import Motor

        # BeforeValidator strips '+' so value becomes "2", but "Years" is
        # not in the conversion map so unit stays unchanged
        motor = Motor(product_name="Test", manufacturer="Test", warranty="2;Years")
        assert motor.warranty == "2;Years"
