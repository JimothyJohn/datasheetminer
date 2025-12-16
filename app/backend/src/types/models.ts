/**
 * TypeScript types for the application data models.
 */

export interface ValueUnit {
  value: number;
  unit: string;
}

export interface MinMaxUnit {
  min: number;
  max: number;
  unit: string;
}

export interface Datasheet {
  datasheet_id?: string;
  url: string;
  pages?: number[];
  product_type: string;
  product_name: string;
  product_family?: string;
  category?: string;
  manufacturer?: string;
  release_year?: number;
  warranty?: ValueUnit;
  PK?: string;
  SK?: string;
}

export interface Dimensions {
  length?: ValueUnit;
  width?: ValueUnit;
  height?: ValueUnit;
}

/**
 * Base interface for all products
 */
export interface ProductBase {
  product_id: string;
  product_type: string;
  product_family?: string;
  component_type?: string;
  manufacturer?: string;
  product_name?: string;
  part_number?: string;
  dimensions?: Dimensions;
  weight?: ValueUnit;
  datasheet_url?: string;
  pages?: number[];
  PK: string;
  SK: string;
}

/**
 * Motor types
 */
export type MotorType =
  | 'brushless dc'
  | 'brushed dc'
  | 'ac induction'
  | 'ac synchronous'
  | 'ac servo'
  | 'permanent magnet'
  | 'hybrid';

/**
 * Motor model matching datasheetminer/models/motor.py
 */
export interface Motor extends ProductBase {
  product_type: 'motor';
  type?: MotorType;
  series?: string;
  rated_voltage?: MinMaxUnit;
  rated_speed?: ValueUnit;
  rated_torque?: ValueUnit;
  peak_torque?: ValueUnit;
  rated_power?: ValueUnit;
  encoder_feedback_support?: string;
  poles?: number;
  rated_current?: ValueUnit;
  peak_current?: ValueUnit;
  voltage_constant?: ValueUnit;
  torque_constant?: ValueUnit;
  resistance?: ValueUnit;
  inductance?: ValueUnit;
  ip_rating?: number;
  rotor_inertia?: ValueUnit;
}

/**
 * Drive types
 */
export type DriveType = 'servo' | 'variable frequency';

/**
 * Drive model matching datasheetminer/models/drive.py
 */
export interface Drive extends ProductBase {
  product_type: 'drive';
  type?: DriveType;
  series?: string;
  input_voltage?: MinMaxUnit;
  input_voltage_frequency?: ValueUnit[];
  input_voltage_phases?: number[];
  rated_current?: ValueUnit;
  peak_current?: ValueUnit;
  output_power?: ValueUnit;
  switching_frequency?: ValueUnit[];
  fieldbus?: string[];
  control_modes?: string[];
  encoder_feedback_support?: string[];
  ethernet_ports?: number;
  digital_inputs?: number;
  digital_outputs?: number;
  analog_inputs?: number;
  analog_outputs?: number;
  safety_features?: string[];
  safety_rating?: string[];
  approvals?: string[];
  max_humidity?: number;
  ip_rating?: number;
  ambient_temp?: MinMaxUnit;
}

/**
 * Union type for all products
 */
export type Product = Motor | Drive | Datasheet;
export type ProductType = 'motor' | 'drive' | 'datasheet' | 'all';
