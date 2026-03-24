//! Unit normalization for datasheet specifications.
//!
//! Converts common unit variants to canonical forms so that all products
//! store specs in consistent, comparable units. Unknown units pass through
//! unchanged.
//!
//! Intentionally excluded (too context-dependent):
//! - Length (m/in/cm/ft)
//! - Frequency (kHz/MHz)
//! - Mass (lb/oz)
//! - Voltage (mV/kV)

use std::f64::consts::PI;

use phf::phf_map;
use tracing::info;

/// A conversion entry: canonical unit name and multiplier.
/// `None` multiplier means special-case conversion (temperature).
struct ConversionEntry {
    canonical: &'static str,
    multiplier: Option<f64>,
}

/// Alias → (canonical_unit, multiplier). Built at compile time via `phf`.
static ALIAS_MAP: phf::Map<&'static str, ConversionEntry> = phf_map! {
    // Torque → Nm
    "mNm"    => ConversionEntry { canonical: "Nm", multiplier: Some(1e-3) },
    "mnm"    => ConversionEntry { canonical: "Nm", multiplier: Some(1e-3) },
    "\u{03bc}Nm" => ConversionEntry { canonical: "Nm", multiplier: Some(1e-6) },
    "oz-in"  => ConversionEntry { canonical: "Nm", multiplier: Some(7.0615518e-3) },
    "oz\u{00b7}in" => ConversionEntry { canonical: "Nm", multiplier: Some(7.0615518e-3) },
    "ozin"   => ConversionEntry { canonical: "Nm", multiplier: Some(7.0615518e-3) },
    "lb-ft"  => ConversionEntry { canonical: "Nm", multiplier: Some(1.3558179) },
    "lb\u{00b7}ft" => ConversionEntry { canonical: "Nm", multiplier: Some(1.3558179) },
    "lbft"   => ConversionEntry { canonical: "Nm", multiplier: Some(1.3558179) },
    "lb-in"  => ConversionEntry { canonical: "Nm", multiplier: Some(0.1129848) },
    "lb\u{00b7}in" => ConversionEntry { canonical: "Nm", multiplier: Some(0.1129848) },
    "lbin"   => ConversionEntry { canonical: "Nm", multiplier: Some(0.1129848) },
    "kgf\u{00b7}cm" => ConversionEntry { canonical: "Nm", multiplier: Some(0.0980665) },
    "kgf.cm" => ConversionEntry { canonical: "Nm", multiplier: Some(0.0980665) },
    "kgfcm"  => ConversionEntry { canonical: "Nm", multiplier: Some(0.0980665) },
    "kNm"    => ConversionEntry { canonical: "Nm", multiplier: Some(1e3) },
    // Power → W
    "mW"     => ConversionEntry { canonical: "W", multiplier: Some(1e-3) },
    "kW"     => ConversionEntry { canonical: "W", multiplier: Some(1e3) },
    "hp"     => ConversionEntry { canonical: "W", multiplier: Some(745.69987) },
    "HP"     => ConversionEntry { canonical: "W", multiplier: Some(745.69987) },
    // Current → A
    "mA"     => ConversionEntry { canonical: "A", multiplier: Some(1e-3) },
    "\u{03bc}A" => ConversionEntry { canonical: "A", multiplier: Some(1e-6) },
    "uA"     => ConversionEntry { canonical: "A", multiplier: Some(1e-6) },
    // Force → N
    "mN"     => ConversionEntry { canonical: "N", multiplier: Some(1e-3) },
    "kN"     => ConversionEntry { canonical: "N", multiplier: Some(1e3) },
    "lbf"    => ConversionEntry { canonical: "N", multiplier: Some(4.4482216) },
    "kgf"    => ConversionEntry { canonical: "N", multiplier: Some(9.80665) },
    // Rotational speed → rpm
    "rad/s"  => ConversionEntry { canonical: "rpm", multiplier: Some(60.0 / (2.0 * PI)) },
    "rps"    => ConversionEntry { canonical: "rpm", multiplier: Some(60.0) },
    // Inertia → kg·cm²
    "g\u{00b7}cm\u{00b2}" => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e-3) },
    "gcm\u{00b2}"  => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e-3) },
    "g.cm\u{00b2}"  => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e-3) },
    "g\u{00b7}cm2"  => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e-3) },
    "gcm2"   => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e-3) },
    "kg\u{00b7}m\u{00b2}" => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e4) },
    "kgm\u{00b2}"  => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e4) },
    "kg.m\u{00b2}"  => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e4) },
    "kg\u{00b7}m2"  => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e4) },
    "kgm2"   => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(1e4) },
    "oz-in\u{00b2}" => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(0.0720078) },
    "oz\u{00b7}in\u{00b2}" => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(0.0720078) },
    "oz-in2" => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(0.0720078) },
    "oz\u{00b7}in2" => ConversionEntry { canonical: "kg\u{00b7}cm\u{00b2}", multiplier: Some(0.0720078) },
    // Inductance → mH
    "H"      => ConversionEntry { canonical: "mH", multiplier: Some(1e3) },
    "\u{03bc}H" => ConversionEntry { canonical: "mH", multiplier: Some(1e-3) },
    "uH"     => ConversionEntry { canonical: "mH", multiplier: Some(1e-3) },
    "nH"     => ConversionEntry { canonical: "mH", multiplier: Some(1e-6) },
    // Resistance → Ω
    "m\u{03a9}" => ConversionEntry { canonical: "\u{03a9}", multiplier: Some(1e-3) },
    "k\u{03a9}" => ConversionEntry { canonical: "\u{03a9}", multiplier: Some(1e3) },
    "ohm"    => ConversionEntry { canonical: "\u{03a9}", multiplier: Some(1.0) },
    "ohms"   => ConversionEntry { canonical: "\u{03a9}", multiplier: Some(1.0) },
    "Ohm"    => ConversionEntry { canonical: "\u{03a9}", multiplier: Some(1.0) },
    "Ohms"   => ConversionEntry { canonical: "\u{03a9}", multiplier: Some(1.0) },
    // Temperature → °C
    "\u{00b0}F" => ConversionEntry { canonical: "\u{00b0}C", multiplier: None },
};

fn convert_temperature(value: f64) -> f64 {
    (value - 32.0) * 5.0 / 9.0
}

/// Round to avoid floating point noise. Keeps up to 6 significant figures.
fn round_converted(value: f64) -> f64 {
    if value == 0.0 {
        return 0.0;
    }
    let magnitude = value.abs().log10().floor() as i32;
    let precision = (5 - magnitude).max(0) as u32;
    let factor = 10_f64.powi(precision as i32);
    (value * factor).round() / factor
}

/// Format a converted float: whole numbers become ints, otherwise use compact notation.
fn format_value(value: f64) -> String {
    if value == value.trunc() && value.abs() < 1e12 {
        format!("{}", value as i64)
    } else {
        format!("{:.*}", 10, value)
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_string()
    }
}

/// Normalize a value+unit pair to canonical form.
///
/// Returns `(converted_value_str, canonical_unit)`.
/// Unknown or already-canonical units pass through unchanged.
pub fn normalize_unit(value_str: &str, unit: &str) -> (String, String) {
    let unit_clean = unit.trim();

    let entry = match ALIAS_MAP.get(unit_clean) {
        Some(e) => e,
        None => return (value_str.to_string(), unit_clean.to_string()),
    };

    let raw_value: f64 = match value_str.parse() {
        Ok(v) => v,
        Err(_) => return (value_str.to_string(), unit_clean.to_string()),
    };

    let converted = match entry.multiplier {
        Some(m) => raw_value * m,
        None => convert_temperature(raw_value),
    };

    let converted = round_converted(converted);
    let converted_str = format_value(converted);

    info!(
        "Unit conversion: {} {} → {} {}",
        value_str, unit_clean, converted_str, entry.canonical
    );
    (converted_str, entry.canonical.to_string())
}

/// Normalize a `"value;unit"` or `"min-max;unit"` compact string to canonical form.
pub fn normalize_value_unit(compact: &str) -> String {
    let Some((value_part, unit)) = compact.split_once(';') else {
        return compact.to_string();
    };

    // Try range pattern: e.g. "20-40" or "-20-40" or "-20--40"
    if let Some((min_str, max_str)) = split_range(value_part) {
        let (min_converted, canonical) = normalize_unit(min_str, unit);
        let (max_converted, _) = normalize_unit(max_str, unit);
        return format!("{}-{};{}", min_converted, max_converted, canonical);
    }

    let (converted_value, canonical) = normalize_unit(value_part, unit);
    format!("{};{}", converted_value, canonical)
}

/// Split a range value like "20-40", "-20-40", or "-20--40" into (min, max).
/// Returns None for single values.
fn split_range(value_part: &str) -> Option<(&str, &str)> {
    // Match pattern: optional negative number, dash, optional negative number
    // Skip the first char if negative, then look for a dash separator
    let search_start = if value_part.starts_with('-') { 1 } else { 0 };
    let rest = &value_part[search_start..];

    // Find a dash that separates two numbers (not a leading negative)
    if let Some(dash_pos) = rest.find('-') {
        let abs_pos = search_start + dash_pos;
        let min_str = &value_part[..abs_pos];
        let max_str = &value_part[abs_pos + 1..];

        // Validate both parts look numeric
        if !min_str.is_empty()
            && !max_str.is_empty()
            && min_str.parse::<f64>().is_ok()
            && max_str.parse::<f64>().is_ok()
        {
            return Some((min_str, max_str));
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- Torque ---
    #[test]
    fn test_mnm_to_nm() {
        let (val, unit) = normalize_unit("500", "mNm");
        assert_eq!(val, "0.5");
        assert_eq!(unit, "Nm");
    }

    #[test]
    fn test_oz_in_to_nm() {
        let (val, unit) = normalize_unit("100", "oz-in");
        assert_eq!(unit, "Nm");
        let v: f64 = val.parse().unwrap();
        assert!((v - 0.706155).abs() < 0.001);
    }

    #[test]
    fn test_lb_ft_to_nm() {
        let (val, unit) = normalize_unit("1", "lb-ft");
        assert_eq!(unit, "Nm");
        let v: f64 = val.parse().unwrap();
        assert!((v - 1.35582).abs() < 0.001);
    }

    #[test]
    fn test_kgf_cm_to_nm() {
        let (val, unit) = normalize_unit("10", "kgf.cm");
        assert_eq!(unit, "Nm");
        let v: f64 = val.parse().unwrap();
        assert!((v - 0.980665).abs() < 0.001);
    }

    #[test]
    fn test_knm_to_nm() {
        let (val, unit) = normalize_unit("2", "kNm");
        assert_eq!(val, "2000");
        assert_eq!(unit, "Nm");
    }

    // --- Power ---
    #[test]
    fn test_mw_to_w() {
        let (val, unit) = normalize_unit("500", "mW");
        assert_eq!(val, "0.5");
        assert_eq!(unit, "W");
    }

    #[test]
    fn test_kw_to_w() {
        let (val, unit) = normalize_unit("1.5", "kW");
        assert_eq!(val, "1500");
        assert_eq!(unit, "W");
    }

    #[test]
    fn test_hp_to_w() {
        let (val, unit) = normalize_unit("1", "hp");
        assert_eq!(unit, "W");
        let v: f64 = val.parse().unwrap();
        assert!((v - 745.7).abs() < 1.0);
    }

    // --- Current ---
    #[test]
    fn test_ma_to_a() {
        let (val, unit) = normalize_unit("500", "mA");
        assert_eq!(val, "0.5");
        assert_eq!(unit, "A");
    }

    #[test]
    fn test_ua_to_a() {
        let (val, unit) = normalize_unit("100", "uA");
        assert_eq!(unit, "A");
        let v: f64 = val.parse().unwrap();
        assert!((v - 0.0001).abs() < 1e-6);
    }

    // --- Force ---
    #[test]
    fn test_kn_to_n() {
        let (val, unit) = normalize_unit("5", "kN");
        assert_eq!(val, "5000");
        assert_eq!(unit, "N");
    }

    #[test]
    fn test_lbf_to_n() {
        let (val, unit) = normalize_unit("10", "lbf");
        assert_eq!(unit, "N");
        let v: f64 = val.parse().unwrap();
        assert!((v - 44.482).abs() < 0.01);
    }

    #[test]
    fn test_kgf_to_n() {
        let (val, unit) = normalize_unit("1", "kgf");
        assert_eq!(unit, "N");
        let v: f64 = val.parse().unwrap();
        assert!((v - 9.80665).abs() < 0.001);
    }

    // --- Speed ---
    #[test]
    fn test_rad_s_to_rpm() {
        let (val, unit) = normalize_unit("314.159", "rad/s");
        assert_eq!(unit, "rpm");
        let v: f64 = val.parse().unwrap();
        assert!((v - 3000.0).abs() < 5.0);
    }

    #[test]
    fn test_rps_to_rpm() {
        let (val, unit) = normalize_unit("50", "rps");
        assert_eq!(val, "3000");
        assert_eq!(unit, "rpm");
    }

    // --- Inertia ---
    #[test]
    fn test_gcm2_to_kgcm2() {
        let (val, unit) = normalize_unit("500", "g\u{00b7}cm\u{00b2}");
        assert_eq!(val, "0.5");
        assert_eq!(unit, "kg\u{00b7}cm\u{00b2}");
    }

    #[test]
    fn test_kgm2_to_kgcm2() {
        let (val, unit) = normalize_unit("0.001", "kg\u{00b7}m\u{00b2}");
        assert_eq!(val, "10");
        assert_eq!(unit, "kg\u{00b7}cm\u{00b2}");
    }

    // --- Inductance ---
    #[test]
    fn test_h_to_mh() {
        let (val, unit) = normalize_unit("0.5", "H");
        assert_eq!(val, "500");
        assert_eq!(unit, "mH");
    }

    #[test]
    fn test_uh_to_mh() {
        let (val, unit) = normalize_unit("100", "uH");
        assert_eq!(val, "0.1");
        assert_eq!(unit, "mH");
    }

    // --- Resistance ---
    #[test]
    fn test_ohm_text_to_symbol() {
        let (val, unit) = normalize_unit("10", "ohm");
        assert_eq!(val, "10");
        assert_eq!(unit, "\u{03a9}");
    }

    #[test]
    fn test_kohm_to_ohm() {
        let (val, unit) = normalize_unit("10", "k\u{03a9}");
        assert_eq!(val, "10000");
        assert_eq!(unit, "\u{03a9}");
    }

    // --- Temperature ---
    #[test]
    fn test_fahrenheit_to_celsius() {
        let (val, unit) = normalize_unit("212", "\u{00b0}F");
        assert_eq!(val, "100");
        assert_eq!(unit, "\u{00b0}C");
    }

    #[test]
    fn test_fahrenheit_negative() {
        let (val, unit) = normalize_unit("-40", "\u{00b0}F");
        assert_eq!(val, "-40");
        assert_eq!(unit, "\u{00b0}C");
    }

    // --- Passthrough ---
    #[test]
    fn test_canonical_unit_passes_through() {
        let (val, unit) = normalize_unit("3000", "rpm");
        assert_eq!(val, "3000");
        assert_eq!(unit, "rpm");
    }

    #[test]
    fn test_unknown_unit_passes_through() {
        let (val, unit) = normalize_unit("100", "widgets");
        assert_eq!(val, "100");
        assert_eq!(unit, "widgets");
    }

    #[test]
    fn test_non_numeric_value_passes_through() {
        let (val, unit) = normalize_unit("2+", "mNm");
        assert_eq!(val, "2+");
        assert_eq!(unit, "mNm");
    }

    #[test]
    fn test_length_units_not_converted() {
        let (val, unit) = normalize_unit("4.5", "m");
        assert_eq!(val, "4.5");
        assert_eq!(unit, "m");
    }

    #[test]
    fn test_khz_not_converted() {
        let (val, unit) = normalize_unit("8", "kHz");
        assert_eq!(val, "8");
        assert_eq!(unit, "kHz");
    }

    // --- normalize_value_unit ---
    #[test]
    fn test_compact_single_value() {
        assert_eq!(normalize_value_unit("500;mNm"), "0.5;Nm");
    }

    #[test]
    fn test_compact_range() {
        assert_eq!(normalize_value_unit("100-500;mA"), "0.1-0.5;A");
    }

    #[test]
    fn test_compact_canonical_passthrough() {
        assert_eq!(normalize_value_unit("3000;rpm"), "3000;rpm");
    }

    #[test]
    fn test_compact_unknown_unit_passthrough() {
        assert_eq!(normalize_value_unit("200-240;V"), "200-240;V");
    }

    #[test]
    fn test_compact_no_semicolon() {
        assert_eq!(normalize_value_unit("hello"), "hello");
    }

    #[test]
    fn test_compact_vac_not_converted() {
        assert_eq!(normalize_value_unit("100-240;VAC"), "100-240;VAC");
    }

    #[test]
    fn test_compact_degrees_not_converted() {
        assert_eq!(normalize_value_unit("360;deg"), "360;deg");
    }

    // --- split_range ---
    #[test]
    fn test_split_range_positive() {
        assert_eq!(split_range("20-40"), Some(("20", "40")));
    }

    #[test]
    fn test_split_range_negative_start() {
        assert_eq!(split_range("-20-40"), Some(("-20", "40")));
    }

    #[test]
    fn test_split_range_single_value() {
        assert_eq!(split_range("20"), None);
    }

    #[test]
    fn test_split_range_negative_single() {
        assert_eq!(split_range("-20"), None);
    }
}
