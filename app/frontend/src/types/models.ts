/**
 * Type definitions matching the backend API
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
  url: string;
  pages?: number[];
}

export interface Dimensions {
  length?: ValueUnit;
  width?: ValueUnit;
  height?: ValueUnit;
}

export interface ProductBase {
  product_id: string;
  product_type: string;
  manufacturer?: string;
  part_number?: string;
  datasheet_url?: Datasheet;
  dimensions?: Dimensions;
  weight?: ValueUnit;
  PK: string;
  SK: string;
}

export type MotorType =
  | 'brushless dc'
  | 'brushed dc'
  | 'ac induction'
  | 'ac synchronous'
  | 'ac servo'
  | 'permanent magnet'
  | 'hybrid';

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

export type DriveType = 'servo' | 'variable frequency';

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

export type Product = Motor | Drive;
export type ProductType = 'motor' | 'drive' | 'all';

export interface ProductSummary {
  total: number;
  motors: number;
  drives: number;
}
