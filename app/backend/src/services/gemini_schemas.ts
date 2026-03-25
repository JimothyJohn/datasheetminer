
import { Type } from '@google/genai';

// Common definitions to reuse
const VALUE_UNIT_DESC = "Format: 'value;unit'. Example: '5.0;A'";
const MIN_MAX_UNIT_DESC = "Format: 'min-max;unit' or 'val;unit'. Example: '10-20;V'";

export const GEMINI_MOTOR_SCHEMA = {
  type: Type.ARRAY,
  items: {
    type: Type.OBJECT,
    properties: {
      type: {
        type: Type.STRING,
        enum: [
          'brushless dc',
          'brushed dc',
          'ac induction',
          'ac synchronous',
          'ac servo',
          'permanent magnet',
          'hybrid',
        ],
      },
      series: { type: Type.STRING },
      rated_voltage: { type: Type.STRING, description: MIN_MAX_UNIT_DESC },
      rated_speed: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_speed: { type: Type.STRING, description: VALUE_UNIT_DESC },
      rated_torque: { type: Type.STRING, description: VALUE_UNIT_DESC },
      peak_torque: { type: Type.STRING, description: VALUE_UNIT_DESC },
      rated_power: { type: Type.STRING, description: VALUE_UNIT_DESC },
      encoder_feedback_support: { type: Type.STRING },
      poles: { type: Type.INTEGER },
      rated_current: { type: Type.STRING, description: VALUE_UNIT_DESC },
      peak_current: { type: Type.STRING, description: VALUE_UNIT_DESC },
      voltage_constant: { type: Type.STRING, description: VALUE_UNIT_DESC },
      torque_constant: { type: Type.STRING, description: VALUE_UNIT_DESC },
      resistance: { type: Type.STRING, description: VALUE_UNIT_DESC },
      inductance: { type: Type.STRING, description: VALUE_UNIT_DESC },
      ip_rating: { type: Type.INTEGER },
      rotor_inertia: { type: Type.STRING, description: VALUE_UNIT_DESC },
      part_number: { type: Type.STRING },
      manufacturer: { type: Type.STRING, description: "The actual manufacturer of this product. Must be a real company name." },
    },
    required: ["part_number"],
  },
};

export const GEMINI_DRIVE_SCHEMA = {
  type: Type.ARRAY,
  items: {
    type: Type.OBJECT,
    properties: {
      type: {
        type: Type.STRING,
        enum: ['servo', 'variable frequency'],
      },
      series: { type: Type.STRING },
      input_voltage: { type: Type.STRING, description: MIN_MAX_UNIT_DESC },
      input_voltage_frequency: {
        type: Type.ARRAY,
        items: { type: Type.STRING, description: VALUE_UNIT_DESC }
      },
      input_voltage_phases: {
        type: Type.ARRAY,
        items: { type: Type.INTEGER }
      },
      rated_current: { type: Type.STRING, description: VALUE_UNIT_DESC },
      peak_current: { type: Type.STRING, description: VALUE_UNIT_DESC },
      output_power: { type: Type.STRING, description: VALUE_UNIT_DESC },
      switching_frequency: {
        type: Type.ARRAY,
        items: { type: Type.STRING, description: VALUE_UNIT_DESC }
      },
      fieldbus: {
        type: Type.ARRAY,
        items: { type: Type.STRING }
      },
      encoder_feedback_support: {
        type: Type.ARRAY,
        items: { type: Type.STRING }
      },
      ethernet_ports: { type: Type.INTEGER },
      digital_inputs: { type: Type.INTEGER },
      digital_outputs: { type: Type.INTEGER },
      analog_inputs: { type: Type.INTEGER },
      analog_outputs: { type: Type.INTEGER },
      safety_rating: {
        type: Type.ARRAY,
        items: { type: Type.STRING }
      },
      approvals: {
        type: Type.ARRAY,
        items: { type: Type.STRING }
      },
      max_humidity: { type: Type.NUMBER },
      ip_rating: { type: Type.INTEGER },
      ambient_temp: { type: Type.STRING, description: MIN_MAX_UNIT_DESC },
      part_number: { type: Type.STRING },
      manufacturer: { type: Type.STRING, description: "The actual manufacturer of this product. Must be a real company name." },
    },
    required: ["part_number"],
  },
};

export const GEMINI_GEARHEAD_SCHEMA = {
  type: Type.ARRAY,
  items: {
    type: Type.OBJECT,
    properties: {
      gear_ratio: { type: Type.NUMBER, description: "Ratio of input speed to output speed (e.g., 10.0 for 10:1)" },
      gear_type: { type: Type.STRING, description: "Type of gear mechanism (e.g., 'planetary', 'spur', 'helical', 'cycloidal', 'harmonic', 'worm', 'bevel')" },
      stages: { type: Type.INTEGER, description: "Number of gear stages" },
      nominal_input_speed: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_input_speed: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_continuous_torque: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_peak_torque: { type: Type.STRING, description: VALUE_UNIT_DESC },
      backlash: { type: Type.STRING, description: VALUE_UNIT_DESC },
      efficiency: { type: Type.NUMBER, description: "Efficiency as a ratio 0-1 (e.g., 0.97 for 97%)" },
      torsional_rigidity: { type: Type.STRING, description: VALUE_UNIT_DESC },
      rotor_inertia: { type: Type.STRING, description: VALUE_UNIT_DESC },
      noise_level: { type: Type.STRING, description: VALUE_UNIT_DESC },
      frame_size: { type: Type.STRING, description: "Frame/flange size designation" },
      input_shaft_diameter: { type: Type.STRING, description: VALUE_UNIT_DESC },
      output_shaft_diameter: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_radial_load: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_axial_load: { type: Type.STRING, description: VALUE_UNIT_DESC },
      ip_rating: { type: Type.STRING, description: "Ingress Protection rating (e.g., IP65)" },
      operating_temp: { type: Type.STRING, description: MIN_MAX_UNIT_DESC },
      service_life: { type: Type.STRING, description: VALUE_UNIT_DESC },
      lubrication_type: { type: Type.STRING },
      weight: { type: Type.STRING, description: VALUE_UNIT_DESC },
      part_number: { type: Type.STRING },
      manufacturer: { type: Type.STRING, description: "The actual manufacturer of this product. Must be a real company name." },
    },
    required: ["part_number"],
  },
};

export const GEMINI_ROBOT_ARM_SCHEMA = {
  type: Type.ARRAY,
  items: {
    type: Type.OBJECT,
    properties: {
      payload: { type: Type.STRING, description: VALUE_UNIT_DESC },
      reach: { type: Type.STRING, description: VALUE_UNIT_DESC },
      degrees_of_freedom: { type: Type.INTEGER, description: "Number of rotating joints/axes" },
      pose_repeatability: { type: Type.STRING, description: VALUE_UNIT_DESC },
      max_tcp_speed: { type: Type.STRING, description: VALUE_UNIT_DESC },
      ip_rating: { type: Type.STRING, description: "Ingress Protection rating (e.g., IP54)" },
      cleanroom_class: { type: Type.STRING, description: "ISO cleanroom classification" },
      noise_level: { type: Type.STRING, description: VALUE_UNIT_DESC },
      mounting_position: { type: Type.STRING, description: "Allowed mounting positions (e.g., 'Any Orientation', 'Floor', 'Ceiling')" },
      operating_temp: { type: Type.STRING, description: MIN_MAX_UNIT_DESC },
      weight: { type: Type.STRING, description: VALUE_UNIT_DESC },
      materials: { type: Type.ARRAY, items: { type: Type.STRING } },
      safety_certifications: { type: Type.ARRAY, items: { type: Type.STRING } },
      part_number: { type: Type.STRING },
      manufacturer: { type: Type.STRING, description: "The actual manufacturer of this product. Must be a real company name." },
    },
    required: ["part_number"],
  },
};

export const SCHEMAS: Record<string, any> = {
  motor: GEMINI_MOTOR_SCHEMA,
  drive: GEMINI_DRIVE_SCHEMA,
  gearhead: GEMINI_GEARHEAD_SCHEMA,
  robot_arm: GEMINI_ROBOT_ARM_SCHEMA,
};
