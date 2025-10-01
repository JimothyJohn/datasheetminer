# Data Schema Examples

This document provides example JSON schemas for extracting structured data from technical datasheets. Use these as templates when crafting prompts for the Datasheet Miner.

## Motor Schema

```json
[
    {
        "model": "1234A",
        "series": "Unitron HD",
        "input_voltage_v": {
            "min": 200,
            "max": 240,
        },
        "manufacturer": "acme",
        "release_year": 2022,
        "rated_speed_rpm": 3794,
        "rated_torque_nm": 1.30,
        "peak_torque_nm": 1.38,
        "rated_torque_lb_in": 11.5,
        "rated_power_kw": 0.52,
        "encoder_feedback_support": "Quadrature",
        "poles": 8,
        "rated_current_a": 1.1,
        "peak_current_a": 6.6,
        "weight_kg": 2,
        "dimensions_mm": { "width": 40, "depth": 174, "height": 233 },
        "voltage_constant_vrms_krpm": 51.63,
        "torque_constant_nm_a": 0.854,
        "resistance_ohm": 11.00,
        "inductance_mh": 47,
        "ip_rating": 54,
        "rotor_inertia_kg_m2": 0.00004407,
    }
]
```

### Example Prompt

```
Extract motor specifications and format as JSON with the following fields:
model, series, manufacturer, input voltage range (min/max), rated speed,
rated torque, peak torque, rated power, encoder support, poles, current ratings,
weight, dimensions, voltage/torque constants, resistance, inductance, IP rating,
and rotor inertia. Return only the JSON data.
```

## Drive/Servo Schema

```json
{
    "model": "Servopotaumus",
    "series": "Hydro HD",
    "manufacturer": "acme",
    "release_year": 2022,
    "input_voltage_v": {
        "min": 200,
        "max": 240,
    },
    "frequency_hz": [50, 60],
    "phases": [1, 3], 
    "rated_current_a": 1.1,
    "peak_current_a": 6.6,
    "output_power_kw": 0.18,
    "output_power_hp": 0.25,
    "switching_frequency_khz": [2,3,4,6,8,12,16],
    "dimensions": {"width": 40, "depth": 174, "height": 233},
    "fieldbus": ["EtherCAT"],
    "control_modes": [
      "Position control",
      "Speed control",
      "Torque control",
      "V/F",
      "Open loop vector",
      "Rotor flux control-Asynchronous",
      "Rotor flux control-Synchronous"
    ],
    "encoder_feedback_support": [
      "Resolver",
      "Quadrature",
      "AB Servo",
      "SinCos",
      "EnDat (2.1/2.2)",
      "SSI",
      "BiSS",
      "Hiperface"
    ],
    "ethernet_ports": 2,
    "digital_inputs": 2,
    "digital_outputs": 2,
    "analog_inputs": 1,
    "analog_outputs": 0,
    "safety_features": ["STO"],
    "safety_rating": ["SIL3", "PLe"],
    "approvals": ["CE", "UL"] ,
    "humidity": 0.95,
    "weight_kg": 1,
    "ip_rating": 20,
    "warranty_yrs": 2,
    "max_ambient_temp_c": 55,
    "min_ambient_temp_c": -20
}
```

### Example Prompt

```
Extract servo drive specifications and return as JSON including: model, series,
manufacturer, input voltage/frequency/phases, current ratings, output power,
switching frequency, dimensions, supported fieldbuses, control modes,
encoder types, I/O counts, safety features, certifications, environmental
ratings, and warranty. Format as structured JSON.
```

## Communication Protocols

### Encoder Protocol

```json
{
    "name": "quadrature",
    "ppr": 4000,
    "absolute": false,
    "input_power": {}, # ttl 
}
```

### Industrial Fieldbus

```json
[
    {
        "name": "RS-232",
        "input_voltage": {ttl},
        "communication_frequency_khz": 9.6,
    },
    {
        "name": "EtherCAT",
        "input_voltage": {ttl},
        "communication_frequency_khz": 100000000,
    }
    {
        "name": "Ethernet/IP",
        "input_voltage": {ttl},
    }
]
```

## Power Input Specifications

Common power input specifications for industrial equipment:

```json
[{
    "name": "200V1ph",
    "min_voltage_v": 170,
    "max_voltage_v": 240,
    "max_current_a": 20,
    "phases": 1,
    "frequency_ hz": 60
},
{
    "name": "ttl",
    "min_voltage_v": 3.3,
    "max_voltage_v": 5.5,
    "max_current_a": 0.5,
    "phases": 1,
    "frequency_ khz": 4
},
{
    "name": "servo_bus_hp",
    "min_voltage_v": 500,
    "max_voltage_v": 700,
    "phases": 3,
    "frequency_ khz": 16 
}
]
```

## Mechanical Power Transmission

### Gearbox Specifications

```json
{
    "max_input_bore_diameter_mm": 20,
    "ratio": 20,
    "stages": 2
}
```

### Drivetrain Specifications

```json
{
    "max_input_bore_diameter_mm": 20,
    "gear_ratio": 20,
    "efficiency": 0.95,
    "max_torque_nm": 100
}
```

## Usage Notes

These schemas serve as templates for structuring extraction prompts. When using the Datasheet Miner:

1. **Reference the schema** in your prompt to get structured output
2. **Customize fields** based on the specific datasheet content
3. **Request JSON format** explicitly in your prompt for parseable output
4. **Validate output** against your expected schema using tools like Pydantic

### Example Extraction Prompt

```
Analyze this motor datasheet and extract specifications in JSON format
following this schema: {model, series, manufacturer, input_voltage_v: {min, max},
rated_speed_rpm, rated_torque_nm, rated_power_kw, weight_kg, dimensions_mm:
{width, depth, height}}. Return only valid JSON, no additional text.
```

## Schema Evolution

As you process more datasheets, refine these schemas to:
- Add new fields discovered in datasheets
- Standardize units and naming conventions
- Create composite schemas for complete system specifications
- Build relationships between motors, drives, and mechanical components
