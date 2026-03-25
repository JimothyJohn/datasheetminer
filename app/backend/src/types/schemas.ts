
import { z } from 'zod';

export const ValueUnitSchema = z.object({
  value: z.number(),
  unit: z.string(),
});

export const MinMaxUnitSchema = z.object({
  min: z.number().optional(),
  max: z.number().optional(),
  unit: z.string(),
});

/**
 * Helper to parse "value;unit" string into ValueUnit object
 */
export const parseValueUnit = (val: string | null | undefined): { value: number, unit: string } | undefined => {
  if (!val) return undefined;
  const parts = val.split(';');
  if (parts.length !== 2) return undefined;
  
  const num = parseFloat(parts[0].trim());
  if (isNaN(num)) return undefined; // Support "2+"? Maybe just strict for now.
  
  return {
    value: num,
    unit: parts[1].trim()
  };
};

/**
 * Helper to parse "min-max;unit" or "val;unit" string into MinMaxUnit object
 */
export const parseMinMaxUnit = (val: string | null | undefined): { min: number, max: number, unit: string } | undefined => {
  if (!val) return undefined;
  const parts = val.split(';');
  if (parts.length !== 2) return undefined;
  
  const unit = parts[1].trim();
  const rangePart = parts[0].trim();
  
  // Check for range "min-max"
  // Needs to handle negative numbers too, e.g. "-20--10"
  // Simple regex: ^(-?[\d.]+)(?:-(-?[\d.]+))?$
  const match = rangePart.match(/^(-?[\d.]+)(?:-(-?[\d.]+))?$/);
  
  if (!match) return undefined;
  
  const v1 = parseFloat(match[1]);
  if (isNaN(v1)) return undefined;
  
  if (match[2]) {
    const v2 = parseFloat(match[2]);
    if (!isNaN(v2)) {
      return { min: v1, max: v2, unit };
    }
  }
  
  // Single value treats as min=max=val for MinMaxUnit? 
  // Or just min=val, max=val?
  return { min: v1, max: v1, unit };
};


// Base Product Schema (Strict)
export const ProductBaseSchema = z.object({
  product_type: z.string(),
  product_name: z.string(),
  product_family: z.string().optional(),
  manufacturer: z.string().optional(),
  datasheet_url: z.string().optional(),
  pages: z.array(z.number()).optional(),
  product_id: z.string().optional(),
  part_number: z.string().optional(),
});

// Motor Schema (Strict)
export const MotorSchema = ProductBaseSchema.extend({
  product_type: z.literal('motor'),
  type: z.enum([
    'brushless dc',
    'brushed dc',
    'ac induction',
    'ac synchronous',
    'ac servo',
    'permanent magnet',
    'hybrid'
  ]).optional(),
  series: z.string().optional(),
  rated_voltage: MinMaxUnitSchema.optional(),
  rated_speed: ValueUnitSchema.optional(),
  max_speed: ValueUnitSchema.optional(),
  rated_torque: ValueUnitSchema.optional(),
  peak_torque: ValueUnitSchema.optional(),
  rated_power: ValueUnitSchema.optional(),
  encoder_feedback_support: z.string().optional(),
  poles: z.number().optional(),
  rated_current: ValueUnitSchema.optional(),
  peak_current: ValueUnitSchema.optional(),
  voltage_constant: ValueUnitSchema.optional(),
  torque_constant: ValueUnitSchema.optional(),
  resistance: ValueUnitSchema.optional(),
  inductance: ValueUnitSchema.optional(),
  ip_rating: z.number().optional(),
  rotor_inertia: ValueUnitSchema.optional(),
});

// Drive Schema (Strict)
export const DriveSchema = ProductBaseSchema.extend({
  product_type: z.literal('drive'),
  type: z.enum(['servo', 'variable frequency']).optional(),
  series: z.string().optional(),
  input_voltage: MinMaxUnitSchema.optional(),
  input_voltage_frequency: z.array(ValueUnitSchema).optional(),
  input_voltage_phases: z.array(z.number()).optional(),
  rated_current: ValueUnitSchema.optional(),
  peak_current: ValueUnitSchema.optional(),
  output_power: ValueUnitSchema.optional(),
  switching_frequency: z.array(ValueUnitSchema).optional(),
  fieldbus: z.array(z.string()).optional(),
  encoder_feedback_support: z.array(z.string()).optional(),
  ethernet_ports: z.number().optional(),
  digital_inputs: z.number().optional(),
  digital_outputs: z.number().optional(),
  analog_inputs: z.number().optional(),
  analog_outputs: z.number().optional(),
  safety_rating: z.array(z.string()).optional(),
  approvals: z.array(z.string()).optional(),
  max_humidity: z.number().optional(),
  ip_rating: z.number().optional(),
  ambient_temp: MinMaxUnitSchema.optional(),
});

// Gearhead Schema
export const GearheadSchema = ProductBaseSchema.extend({
  product_type: z.literal('gearhead'),
  gear_ratio: z.number().optional(),
  gear_type: z.string().optional(),
  stages: z.number().optional(),
  nominal_input_speed: ValueUnitSchema.optional(),
  max_input_speed: ValueUnitSchema.optional(),
  max_continuous_torque: ValueUnitSchema.optional(),
  max_peak_torque: ValueUnitSchema.optional(),
  backlash: ValueUnitSchema.optional(),
  efficiency: z.number().optional(),
  torsional_rigidity: ValueUnitSchema.optional(),
  rotor_inertia: ValueUnitSchema.optional(),
  noise_level: ValueUnitSchema.optional(),
  frame_size: z.string().optional(),
  input_shaft_diameter: ValueUnitSchema.optional(),
  output_shaft_diameter: ValueUnitSchema.optional(),
  max_radial_load: ValueUnitSchema.optional(),
  max_axial_load: ValueUnitSchema.optional(),
  ip_rating: z.string().optional(),
  operating_temp: MinMaxUnitSchema.optional(),
  service_life: ValueUnitSchema.optional(),
  lubrication_type: z.string().optional(),
  weight: ValueUnitSchema.optional(),
});

// Robot Arm Schema
export const RobotArmSchema = ProductBaseSchema.extend({
  product_type: z.literal('robot_arm'),
  payload: ValueUnitSchema.optional(),
  reach: ValueUnitSchema.optional(),
  degrees_of_freedom: z.number().optional(),
  pose_repeatability: ValueUnitSchema.optional(),
  max_tcp_speed: ValueUnitSchema.optional(),
  ip_rating: z.string().optional(),
  cleanroom_class: z.string().optional(),
  noise_level: ValueUnitSchema.optional(),
  mounting_position: z.string().optional(),
  operating_temp: MinMaxUnitSchema.optional(),
  weight: ValueUnitSchema.optional(),
  materials: z.array(z.string()).optional(),
  safety_certifications: z.array(z.string()).optional(),
});

export const DatasheetSchema = z.object({
  datasheet_id: z.string().optional(),
  url: z.string(),
  pages: z.array(z.number()).optional(),
  product_type: z.string(),
  product_name: z.string(),
  product_family: z.string().optional(),
  manufacturer: z.string().optional(),
  last_scraped: z.string().optional(), // ISO string
});
