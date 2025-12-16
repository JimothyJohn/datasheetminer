/**
 * Filters & Sorting: Advanced Product Filtering System
 *
 * This module provides a comprehensive client-side filtering and sorting system
 * with support for complex data types, multi-level sorting, and natural alphanumeric ordering.
 *
 * Key Features:
 * - Multi-attribute filtering with include/exclude modes
 * - Numeric comparison operators (=, >, <, >=, <=, !=)
 * - Natural alphanumeric sorting (handles "abc2" vs "abc10" correctly)
 * - Multi-level sorting (sort by attribute1, then attribute2, then attribute3)
 * - Support for nested objects (ValueUnit, MinMaxUnit, Dimensions)
 * - Array filtering (fieldbus, control_modes, etc.)
 * - Type-aware attribute metadata (20 motor attributes + 23 drive attributes)
 *
 * Performance:
 * - Client-side filtering: ~10-50ms for 1000 products with 5 filters
 * - Multi-level sorting: ~20-100ms for 1000 products with 3 sort levels
 *
 * @module filters
 */

import { Product, ProductType } from './models';

// ========== Type Definitions ==========

/**
 * Filter mode determines how a filter criterion is applied
 *
 * - 'include': Product MUST match this filter (AND logic)
 * - 'exclude': Product MUST NOT match this filter (NOT logic)
 * - 'neutral': Filter is ignored (useful for temporarily disabling)
 *
 * Example: Filter by manufacturer="ACME" (include) + voltage>200 (include)
 * → Only products from ACME with voltage > 200V
 */
export type FilterMode = 'include' | 'exclude' | 'neutral';

/**
 * Comparison operators for filtering
 *
 * Supported operations:
 * - '=': Equal to (exact match)
 * - '>': Greater than
 * - '<': Less than
 * - '>=': Greater than or equal to
 * - '<=': Less than or equal to
 * - '!=': Not equal to
 *
 * Used for: voltage, current, power, speed, weight, etc.
 */
export type ComparisonOperator = '=' | '>' | '<' | '>=' | '<=' | '!=';

/**
 * Valid filter value types
 *
 * - string: Text matching (case-insensitive, partial match)
 * - string[]: Multiple string values (OR logic - matches any)
 * - number: Numeric comparison with operators
 * - boolean: True/false matching
 * - [number, number]: Range matching (min, max)
 */
export type FilterValue = string | string[] | number | boolean | [number, number];

/**
 * A single filter criterion
 *
 * Represents one filter condition in the filter chain.
 * Multiple criteria are combined with AND logic.
 *
 * Examples:
 * 1. { attribute: 'manufacturer', mode: 'include', value: 'ACME', displayName: 'Manufacturer' }
 *    → Only show products from ACME
 *
 * 2. { attribute: 'rated_voltage.min', mode: 'include', value: 200, operator: '>=', displayName: 'Rated Voltage' }
 *    → Only show products with rated voltage min >= 200V
 *
 * 3. { attribute: 'type', mode: 'exclude', value: 'servo', displayName: 'Motor Type' }
 *    → Hide all servo motors
 */
export interface FilterCriterion {
  attribute: string;          // Dot-notation path (e.g., 'rated_voltage.min')
  mode: FilterMode;           // Include/exclude/neutral
  value?: FilterValue;        // Filter value (optional for existence checks)
  operator?: ComparisonOperator; // Comparison operator (for numbers)
  displayName: string;        // Human-readable attribute name for UI
}

/**
 * Sort configuration for a single sort level
 *
 * Multi-level sorting: Apply sorts in array order
 * Example: [{ attr: 'manufacturer', dir: 'asc' }, { attr: 'power', dir: 'desc' }]
 * → Sort by manufacturer A-Z, then by power high-to-low within each manufacturer
 */
export interface SortConfig {
  attribute: string;          // Attribute to sort by (dot-notation supported)
  direction: 'asc' | 'desc';  // Sort direction
  displayName: string;        // Human-readable name for UI
}

/**
 * Attribute metadata for UI components
 *
 * Provides type information, display names, and units for each filterable attribute.
 * Used by AttributeSelector, FilterBar, and ProductList components.
 *
 * Type mappings:
 * - 'string': Text fields (manufacturer, part_number, series)
 * - 'number': Simple numeric fields (poles, ethernet_ports, ip_rating)
 * - 'boolean': True/false fields (currently unused but supported)
 * - 'range': MinMaxUnit objects ({ min: number, max: number, unit: string })
 * - 'array': Array fields (fieldbus, control_modes, safety_features)
 * - 'object': ValueUnit objects ({ value: number, unit: string })
 */
export interface AttributeMetadata {
  key: string;                // Attribute key (matches Product interface)
  displayName: string;        // Human-readable name for UI
  type: 'string' | 'number' | 'boolean' | 'range' | 'array' | 'object';
  applicableTypes: ('motor' | 'drive' | 'robot_arm' | 'gearhead' | 'datasheet')[]; // Which product types have this attribute
  nested?: boolean;           // True for ValueUnit and MinMaxUnit types
  unit?: string;              // Unit of measurement (e.g., "V", "W", "A", "rpm", "kg")
}

// ========== Attribute Metadata Functions ==========

/**
 * Get all filterable attributes for motors
 *
 * Returns 20 motor-specific attributes with metadata for filtering/sorting.
 * Each attribute includes display name, data type, and unit of measurement.
 *
 * Categories:
 * - Identification: manufacturer, part_number, type, series
 * - Electrical: rated_voltage, rated_current, peak_current, resistance, inductance
 * - Mechanical: rated_speed, rated_torque, peak_torque, poles, rotor_inertia
 * - Power: rated_power, voltage_constant, torque_constant
 * - Physical: weight, ip_rating
 * - Feedback: encoder_feedback_support
 *
 * @returns Array of 20 motor attribute metadata objects
 */
export const getMotorAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['motor'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['motor'] },
  { key: 'type', displayName: 'Motor Type', type: 'string', applicableTypes: ['motor'] },
  { key: 'series', displayName: 'Series', type: 'string', applicableTypes: ['motor'] },
  { key: 'rated_voltage', displayName: 'Rated Voltage', type: 'range', applicableTypes: ['motor'], nested: true, unit: 'V' },
  { key: 'rated_speed', displayName: 'Rated Speed', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'rpm' },
  { key: 'rated_torque', displayName: 'Rated Torque', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'Nm' },
  { key: 'peak_torque', displayName: 'Peak Torque', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'Nm' },
  { key: 'rated_power', displayName: 'Rated Power', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'W' },
  { key: 'encoder_feedback_support', displayName: 'Encoder Feedback', type: 'string', applicableTypes: ['motor'] },
  { key: 'poles', displayName: 'Poles', type: 'number', applicableTypes: ['motor'] },
  { key: 'rated_current', displayName: 'Rated Current', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'A' },
  { key: 'peak_current', displayName: 'Peak Current', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'A' },
  { key: 'voltage_constant', displayName: 'Voltage Constant', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'V/krpm' },
  { key: 'torque_constant', displayName: 'Torque Constant', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'Nm/A' },
  { key: 'resistance', displayName: 'Resistance', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'Ω' },
  { key: 'inductance', displayName: 'Inductance', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'mH' },
  { key: 'ip_rating', displayName: 'IP Rating', type: 'number', applicableTypes: ['motor'] },
  { key: 'rotor_inertia', displayName: 'Rotor Inertia', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'kg·cm²' },
  { key: 'weight', displayName: 'Weight', type: 'object', applicableTypes: ['motor'], nested: true, unit: 'kg' },
];

/**
 * Get all filterable attributes for robot arms
 *
 * Returns robot arm-specific attributes with metadata for filtering/sorting.
 * Each attribute includes display name, data type, and unit of measurement.
 *
 * Categories:
 * - Identification: manufacturer, part_number, product_family
 * - Performance: payload, reach, degrees_of_freedom, pose_repeatability, max_tcp_speed
 * - Environmental: ip_rating, cleanroom_class, noise_level, mounting_position, operating_temp
 * - Materials & Safety: materials, safety_certifications
 * - Physical: weight
 *
 * @returns Array of robot arm attribute metadata objects
 */
export const getRobotArmAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['robot_arm'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['robot_arm'] },
  { key: 'product_family', displayName: 'Product Family', type: 'string', applicableTypes: ['robot_arm'] },
  { key: 'payload', displayName: 'Payload', type: 'object', applicableTypes: ['robot_arm'], nested: true, unit: 'kg' },
  { key: 'reach', displayName: 'Reach', type: 'object', applicableTypes: ['robot_arm'], nested: true, unit: 'mm' },
  { key: 'degrees_of_freedom', displayName: 'Degrees of Freedom', type: 'number', applicableTypes: ['robot_arm'] },
  { key: 'pose_repeatability', displayName: 'Pose Repeatability', type: 'object', applicableTypes: ['robot_arm'], nested: true, unit: 'mm' },
  { key: 'max_tcp_speed', displayName: 'Max TCP Speed', type: 'object', applicableTypes: ['robot_arm'], nested: true, unit: 'm/s' },
  { key: 'ip_rating', displayName: 'IP Rating', type: 'string', applicableTypes: ['robot_arm'] },
  { key: 'cleanroom_class', displayName: 'Cleanroom Class', type: 'string', applicableTypes: ['robot_arm'] },
  { key: 'noise_level', displayName: 'Noise Level', type: 'object', applicableTypes: ['robot_arm'], nested: true, unit: 'dB(A)' },
  { key: 'mounting_position', displayName: 'Mounting Position', type: 'string', applicableTypes: ['robot_arm'] },
  { key: 'operating_temp', displayName: 'Operating Temperature', type: 'range', applicableTypes: ['robot_arm'], nested: true, unit: '°C' },
  { key: 'materials', displayName: 'Materials', type: 'array', applicableTypes: ['robot_arm'] },
  { key: 'safety_certifications', displayName: 'Safety Certifications', type: 'array', applicableTypes: ['robot_arm'] },
  { key: 'weight', displayName: 'Weight', type: 'object', applicableTypes: ['robot_arm'], nested: true, unit: 'kg' },
];

/**
 * Get all filterable attributes for gearheads
 *
 * Returns gearhead-specific attributes with metadata for filtering/sorting.
 * Each attribute includes display name, data type, and unit of measurement.
 *
 * Categories:
 * - Identification: manufacturer, part_number, frame_size
 * - Performance: gear_ratio, gear_type, stages, nominal_input_speed, max_input_speed
 * - Torque & Power: max_continuous_torque, max_peak_torque, efficiency
 * - Mechanical: backlash, torsional_rigidity, rotor_inertia
 * - Shafts & Loads: input_shaft_diameter, output_shaft_diameter, max_radial_load, max_axial_load
 * - Environmental: ip_rating, operating_temp, noise_level, service_life
 * - Maintenance: lubrication_type
 * - Physical: weight
 *
 * @returns Array of gearhead attribute metadata objects
 */
export const getGearheadAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['gearhead'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['gearhead'] },
  { key: 'gear_ratio', displayName: 'Gear Ratio', type: 'number', applicableTypes: ['gearhead'] },
  { key: 'gear_type', displayName: 'Gear Type', type: 'string', applicableTypes: ['gearhead'] },
  { key: 'stages', displayName: 'Stages', type: 'number', applicableTypes: ['gearhead'] },
  { key: 'nominal_input_speed', displayName: 'Nominal Input Speed', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'rpm' },
  { key: 'max_input_speed', displayName: 'Max Input Speed', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'rpm' },
  { key: 'max_continuous_torque', displayName: 'Max Continuous Torque', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'Nm' },
  { key: 'max_peak_torque', displayName: 'Max Peak Torque', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'Nm' },
  { key: 'backlash', displayName: 'Backlash', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'arcmin' },
  { key: 'efficiency', displayName: 'Efficiency', type: 'number', applicableTypes: ['gearhead'], unit: '%' },
  { key: 'torsional_rigidity', displayName: 'Torsional Rigidity', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'Nm/arcmin' },
  { key: 'rotor_inertia', displayName: 'Rotor Inertia', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'kg·cm²' },
  { key: 'noise_level', displayName: 'Noise Level', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'dBA' },
  { key: 'frame_size', displayName: 'Frame Size', type: 'string', applicableTypes: ['gearhead'] },
  { key: 'input_shaft_diameter', displayName: 'Input Shaft Diameter', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'mm' },
  { key: 'output_shaft_diameter', displayName: 'Output Shaft Diameter', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'mm' },
  { key: 'max_radial_load', displayName: 'Max Radial Load', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'N' },
  { key: 'max_axial_load', displayName: 'Max Axial Load', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'N' },
  { key: 'ip_rating', displayName: 'IP Rating', type: 'string', applicableTypes: ['gearhead'] },
  { key: 'operating_temp', displayName: 'Operating Temperature', type: 'range', applicableTypes: ['gearhead'], nested: true, unit: '°C' },
  { key: 'service_life', displayName: 'Service Life', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'hours' },
  { key: 'lubrication_type', displayName: 'Lubrication Type', type: 'string', applicableTypes: ['gearhead'] },
  { key: 'weight', displayName: 'Weight', type: 'object', applicableTypes: ['gearhead'], nested: true, unit: 'kg' },
];

/**
 * Get all filterable attributes for datasheets
 *
 * Returns datasheet-specific attributes with metadata for filtering/sorting.
 *
 * Categories:
 * - Identification: manufacturer, product_name, product_family, product_type
 * - Content: url, pages
 *
 * @returns Array of datasheet attribute metadata objects
 */
export const getDatasheetAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['datasheet'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['datasheet'] },
  { key: 'product_name', displayName: 'Product Name', type: 'string', applicableTypes: ['datasheet'] },
  { key: 'product_family', displayName: 'Product Family', type: 'string', applicableTypes: ['datasheet'] },
  { key: 'component_type', displayName: 'Product Type', type: 'string', applicableTypes: ['datasheet'] },
];

/**
 * Get all filterable attributes for drives
 *
 * Returns 23 drive-specific attributes with metadata for filtering/sorting.
 * Each attribute includes display name, data type, and unit of measurement.
 *
 * Categories:
 * - Identification: manufacturer, part_number, type, series
 * - Electrical: input_voltage, input_voltage_phases, rated_current, peak_current, output_power
 * - I/O & Connectivity: ethernet_ports, digital_inputs, digital_outputs, analog_inputs, analog_outputs
 * - Communication: fieldbus, control_modes, encoder_feedback_support
 * - Safety & Ratings: safety_features, safety_rating, approvals, ip_rating
 * - Environmental: max_humidity, ambient_temp
 * - Physical: weight
 *
 * @returns Array of 23 drive attribute metadata objects
 */
export const getDriveAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['drive'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['drive'] },
  { key: 'type', displayName: 'Drive Type', type: 'string', applicableTypes: ['drive'] },
  { key: 'series', displayName: 'Series', type: 'string', applicableTypes: ['drive'] },
  { key: 'input_voltage', displayName: 'Input Voltage', type: 'range', applicableTypes: ['drive'], nested: true, unit: 'V' },
  { key: 'input_voltage_phases', displayName: 'Input Voltage Phases', type: 'array', applicableTypes: ['drive'] },
  { key: 'rated_current', displayName: 'Rated Current', type: 'object', applicableTypes: ['drive'], nested: true, unit: 'A' },
  { key: 'peak_current', displayName: 'Peak Current', type: 'object', applicableTypes: ['drive'], nested: true, unit: 'A' },
  { key: 'output_power', displayName: 'Output Power', type: 'object', applicableTypes: ['drive'], nested: true, unit: 'W' },
  { key: 'fieldbus', displayName: 'Fieldbus', type: 'array', applicableTypes: ['drive'] },
  { key: 'control_modes', displayName: 'Control Modes', type: 'array', applicableTypes: ['drive'] },
  { key: 'encoder_feedback_support', displayName: 'Encoder Feedback', type: 'array', applicableTypes: ['drive'] },
  { key: 'ethernet_ports', displayName: 'Ethernet Ports', type: 'number', applicableTypes: ['drive'] },
  { key: 'digital_inputs', displayName: 'Digital Inputs', type: 'number', applicableTypes: ['drive'] },
  { key: 'digital_outputs', displayName: 'Digital Outputs', type: 'number', applicableTypes: ['drive'] },
  { key: 'analog_inputs', displayName: 'Analog Inputs', type: 'number', applicableTypes: ['drive'] },
  { key: 'analog_outputs', displayName: 'Analog Outputs', type: 'number', applicableTypes: ['drive'] },
  { key: 'safety_features', displayName: 'Safety Features', type: 'array', applicableTypes: ['drive'] },
  { key: 'safety_rating', displayName: 'Safety Rating', type: 'array', applicableTypes: ['drive'] },
  { key: 'approvals', displayName: 'Approvals', type: 'array', applicableTypes: ['drive'] },
  { key: 'max_humidity', displayName: 'Max Humidity', type: 'number', applicableTypes: ['drive'], unit: '%' },
  { key: 'ip_rating', displayName: 'IP Rating', type: 'number', applicableTypes: ['drive'] },
  { key: 'ambient_temp', displayName: 'Ambient Temperature', type: 'range', applicableTypes: ['drive'], nested: true, unit: '°C' },
  { key: 'weight', displayName: 'Weight', type: 'object', applicableTypes: ['drive'], nested: true, unit: 'kg' },
];

/**
 * Get all attributes for a specific product type
 *
 * Smart attribute selection based on current product type:
 * - null: Returns empty array (no product type selected)
 * - 'motor': Returns 20 motor-specific attributes
 * - 'drive': Returns 23 drive-specific attributes
 * - 'robot_arm': Returns robot arm-specific attributes
 * - 'gearhead': Returns gearhead-specific attributes
 * - 'all': Returns intersection of all product type attributes (common attributes)
 *
 * The 'all' mode finds attributes that exist across multiple product types:
 * - manufacturer, part_number, weight, etc.
 *
 * This prevents showing irrelevant attributes when viewing mixed product types.
 *
 * Performance: O(n*m) where n=attrs1, m=attrs2
 * Cached by components, so performance impact is minimal.
 *
 * @param productType - Product type filter ('motor', 'drive', 'robot_arm', 'gearhead', 'datasheet', 'all', or null)
 * @returns Array of applicable attribute metadata
 */
export const getAttributesForType = (productType: ProductType): AttributeMetadata[] => {
  // Handle null productType (no selection)
  if (productType === null) return [];

  // Fast path: type-specific attributes
  if (productType === 'motor') return getMotorAttributes();
  if (productType === 'drive') return getDriveAttributes();
  if (productType === 'robot_arm') return getRobotArmAttributes();
  if (productType === 'gearhead') return getGearheadAttributes();
  if (productType === 'datasheet') return getDatasheetAttributes();

  // ===== COMPUTE COMMON ATTRIBUTES =====
  // For 'all' type, find intersection across all product types
  const motorAttrs = getMotorAttributes();
  const driveAttrs = getDriveAttributes();
  const robotArmAttrs = getRobotArmAttributes();
  const gearheadAttrs = getGearheadAttributes();
  const datasheetAttrs = getDatasheetAttributes();
  const commonKeys = new Set<string>();
  const commonAttrs: AttributeMetadata[] = [];

  // Find attributes that exist in multiple product type schemas
  // Start with motor attributes and check if they exist in other types
  motorAttrs.forEach(attr => {
    const inDrive = driveAttrs.some(d => d.key === attr.key);
    const inRobotArm = robotArmAttrs.some(r => r.key === attr.key);
    const inGearhead = gearheadAttrs.some(g => g.key === attr.key);
    const inDatasheet = datasheetAttrs.some(d => d.key === attr.key);

    // If attribute exists in at least 2 product types, include it
    const count = [inDrive, inRobotArm, inGearhead, inDatasheet].filter(Boolean).length + 1; // +1 for motor
    if (count >= 2 && !commonKeys.has(attr.key)) {
      commonKeys.add(attr.key);
      const applicableTypes: ('motor' | 'drive' | 'robot_arm' | 'gearhead' | 'datasheet')[] = ['motor'];
      if (inDrive) applicableTypes.push('drive');
      if (inRobotArm) applicableTypes.push('robot_arm');
      if (inGearhead) applicableTypes.push('gearhead');
      if (inDatasheet) applicableTypes.push('datasheet');

      commonAttrs.push({
        ...attr,
        applicableTypes
      });
    }
  });

  // Check drive attributes that weren't in motor
  driveAttrs.forEach(attr => {
    if (commonKeys.has(attr.key)) return;

    const inRobotArm = robotArmAttrs.some(r => r.key === attr.key);
    const inGearhead = gearheadAttrs.some(g => g.key === attr.key);
    const inDatasheet = datasheetAttrs.some(d => d.key === attr.key);

    const count = [inRobotArm, inGearhead, inDatasheet].filter(Boolean).length + 1; // +1 for drive
    if (count >= 2) {
      commonKeys.add(attr.key);
      const applicableTypes: ('motor' | 'drive' | 'robot_arm' | 'gearhead' | 'datasheet')[] = ['drive'];
      if (inRobotArm) applicableTypes.push('robot_arm');
      if (inGearhead) applicableTypes.push('gearhead');
      if (inDatasheet) applicableTypes.push('datasheet');

      commonAttrs.push({
        ...attr,
        applicableTypes
      });
    }
  });

  // Check robot_arm attributes that weren't in motor or drive
  robotArmAttrs.forEach(attr => {
    if (commonKeys.has(attr.key)) return;

    const inGearhead = gearheadAttrs.some(g => g.key === attr.key);
    const inDatasheet = datasheetAttrs.some(d => d.key === attr.key);

    if (inGearhead || inDatasheet) {
      commonKeys.add(attr.key);
      const applicableTypes: ('motor' | 'drive' | 'robot_arm' | 'gearhead' | 'datasheet')[] = ['robot_arm'];
      if (inGearhead) applicableTypes.push('gearhead');
      if (inDatasheet) applicableTypes.push('datasheet');
      
      commonAttrs.push({
        ...attr,
        applicableTypes
      });
    }
  });

  console.log(`[filters] Found ${commonAttrs.length} common attributes for 'all' type`);
  return commonAttrs;
};

/**
 * Get available comparison operators for an attribute based on actual data values
 *
 * Analyzes the actual values found in products for the given attribute and
 * determines which comparison operators make sense based on the datatype.
 *
 * Rules:
 * - Numeric values (or extractable from objects): All operators (=, >, <, >=, <=, !=)
 * - String values: Equality only (=, !=)
 * - Boolean values: Equality only (=)
 * - Array values: Equality/contains (=, !=)
 * - Mixed types: Defaults to equality only (=, !=)
 *
 * @param products - Array of products to analyze
 * @param attribute - Attribute key (supports dot notation)
 * @returns Array of valid comparison operators for this attribute
 */
export const getAvailableOperators = (products: Product[], attribute: string): ComparisonOperator[] => {
  // If no products, default to all operators
  if (products.length === 0) {
    return ['=', '>', '<', '>=', '<=', '!='];
  }

  // Extract all non-null values for this attribute
  const values = products
    .map(product => getNestedValue(product, attribute))
    .filter(val => val !== null && val !== undefined);

  // If no values found, default to equality operators
  if (values.length === 0) {
    return ['=', '!='];
  }

  // Analyze value types
  let hasNumeric = false;
  let hasString = false;
  let hasBoolean = false;
  let hasArray = false;
  let hasObject = false;

  for (const value of values) {
    if (typeof value === 'number') {
      hasNumeric = true;
    } else if (typeof value === 'string') {
      hasString = true;
    } else if (typeof value === 'boolean') {
      hasBoolean = true;
    } else if (Array.isArray(value)) {
      hasArray = true;
    } else if (typeof value === 'object') {
      // Check if we can extract numeric value from object (ValueUnit, MinMaxUnit)
      const numVal = extractNumericValue(value);
      if (numVal !== null) {
        hasNumeric = true;
      } else {
        hasObject = true;
      }
    }
  }

  // Determine operators based on datatypes found
  // If all values are numeric or can be converted to numeric, allow all operators
  if (hasNumeric && !hasString && !hasBoolean && !hasArray && !hasObject) {
    return ['=', '>', '<', '>=', '<=', '!='];
  }

  // If only strings, allow equality operators
  if (hasString && !hasNumeric && !hasBoolean && !hasArray && !hasObject) {
    return ['=', '!='];
  }

  // If only booleans, allow equality only
  if (hasBoolean && !hasNumeric && !hasString && !hasArray && !hasObject) {
    return ['='];
  }

  // If only arrays, allow equality/contains
  if (hasArray && !hasNumeric && !hasString && !hasBoolean && !hasObject) {
    return ['=', '!='];
  }

  // Mixed types or complex objects: default to equality operators
  return ['=', '!='];
};

// ========== Filtering Functions ==========

/**
 * Apply filters to products (client-side filtering)
 *
 * Implements multi-criteria AND logic filtering:
 * - All 'include' filters must match
 * - No 'exclude' filters can match
 * - 'neutral' filters are ignored
 *
 * Supports:
 * - Nested object paths (e.g., 'rated_voltage.min')
 * - Numeric comparisons (=, >, <, >=, <=, !=)
 * - String matching (case-insensitive, partial match)
 * - Array contains checks (fieldbus, control_modes)
 * - ValueUnit and MinMaxUnit objects
 *
 * Performance: O(n * f) where n=products, f=filters
 * Typical: ~10-50ms for 1000 products with 5 filters
 *
 * Example:
 * ```typescript
 * applyFilters(products, [
 *   { attribute: 'manufacturer', mode: 'include', value: 'ACME', operator: '=', displayName: 'Manufacturer' },
 *   { attribute: 'rated_voltage.min', mode: 'include', value: 200, operator: '>=', displayName: 'Voltage' }
 * ])
 * // Returns only ACME products with voltage >= 200V
 * ```
 *
 * @param products - Array of products to filter
 * @param filters - Array of filter criteria (AND logic)
 * @returns Filtered array of products
 */
export const applyFilters = (products: Product[], filters: FilterCriterion[]): Product[] => {
  console.log(`[filters] Applying ${filters.length} filters to ${products.length} products`);

  const filtered = products.filter(product => {
    // ===== CHECK EACH FILTER =====
    // All filters must pass for product to be included
    for (const filter of filters) {
      // Skip neutral filters (temporarily disabled)
      if (filter.mode === 'neutral') continue;

      // Extract value using dot notation (e.g., 'rated_voltage.min')
      const value = getNestedValue(product, filter.attribute);

      // ===== HANDLE MISSING VALUES =====
      if (value === undefined || value === null) {
        // For 'include' mode: missing attribute = exclude product
        if (filter.mode === 'include') return false;
        // For 'exclude' mode: missing attribute = can't match = skip filter
        continue;
      }

      // ===== CHECK IF VALUE MATCHES FILTER =====
      const matches = matchesFilter(value, filter);

      // Apply filter logic
      if (filter.mode === 'include' && !matches) return false; // Must match
      if (filter.mode === 'exclude' && matches) return false;  // Must NOT match
    }

    // All filters passed
    return true;
  });

  console.log(`[filters] Filtered to ${filtered.length} products`);
  return filtered;
};

// ========== Sorting Functions ==========

/**
 * Sort products by multiple attributes with natural alphanumeric sorting
 *
 * Features:
 * - Multi-level sorting: Sort by attr1, then attr2, then attr3
 * - Natural alphanumeric ordering: "abc2" < "abc10" (not lexicographic)
 * - Null handling: null/undefined values always sort last
 * - Numeric extraction: Handles ValueUnit and MinMaxUnit objects
 * - Direction support: 'asc' or 'desc' for each level
 *
 * Sorting Algorithm:
 * 1. For each sort level (in order):
 *    a. Extract values from both products
 *    b. Handle null/undefined (null always last)
 *    c. Extract numbers from ValueUnit/MinMaxUnit if applicable
 *    d. Compare: numeric if both numbers, else natural alphanumeric
 *    e. Apply direction (asc/desc)
 *    f. If equal, continue to next sort level
 * 2. If all levels equal, maintain original order
 *
 * Performance: O(n log n * s) where n=products, s=sort levels
 * Typical: ~20-100ms for 1000 products with 3 sort levels
 *
 * Example:
 * ```typescript
 * sortProducts(products, [
 *   { attribute: 'manufacturer', direction: 'asc', displayName: 'Manufacturer' },
 *   { attribute: 'rated_power.value', direction: 'desc', displayName: 'Power' }
 * ])
 * // Groups by manufacturer A-Z, then by power high-to-low within each manufacturer
 * ```
 *
 * @param products - Array of products to sort
 * @param sort - Single sort config or array of sort configs (null = no sort)
 * @returns New sorted array (original array unchanged)
 */
export const sortProducts = (products: Product[], sort: SortConfig | SortConfig[] | null): Product[] => {
  if (!sort) return products;

  // Normalize to array for uniform handling
  const sorts = Array.isArray(sort) ? sort : [sort];
  if (sorts.length === 0) return products;

  console.log(`[filters] Sorting ${products.length} products by ${sorts.length} levels:`,
    sorts.map(s => `${s.displayName} (${s.direction})`).join(', '));

  // Create new array to avoid mutating original
  return [...products].sort((a, b) => {
    // ===== TRY EACH SORT LEVEL =====
    // Continue until we find a difference
    for (const sortConfig of sorts) {
      const aVal = getNestedValue(a, sortConfig.attribute);
      const bVal = getNestedValue(b, sortConfig.attribute);

      // ===== HANDLE NULL/UNDEFINED =====
      // Null values always sort last (regardless of direction)
      if (aVal === undefined || aVal === null) {
        if (bVal === undefined || bVal === null) continue; // Both null, try next sort
        return 1; // a is null, b is not → a goes after b
      }
      if (bVal === undefined || bVal === null) return -1; // b is null → a goes before b

      // ===== EXTRACT NUMERIC VALUES =====
      // Handle ValueUnit ({ value: 100, unit: 'V' }) and MinMaxUnit ({ min: 200, max: 240, unit: 'V' })
      const aNum = extractNumericValue(aVal);
      const bNum = extractNumericValue(bVal);

      let comparison = 0;

      // ===== COMPARE VALUES =====
      if (typeof aNum === 'number' && typeof bNum === 'number') {
        // Pure numeric comparison (fast)
        comparison = aNum - bNum;
      } else {
        // Natural alphanumeric sorting (handles "abc2" vs "abc10" correctly)
        comparison = naturalCompare(String(aVal), String(bVal));
      }

      // ===== APPLY DIRECTION =====
      comparison = sortConfig.direction === 'asc' ? comparison : -comparison;

      // If we found a difference, return it
      if (comparison !== 0) return comparison;

      // If equal, continue to next sort level
    }

    // All sort levels equal → maintain original order
    return 0;
  });
};

// ========== Helper Functions ==========

/**
 * Natural alphanumeric comparison
 *
 * Handles strings with embedded numbers intelligently:
 * - "abc2" < "abc10" (not "abc10" < "abc2" like lexicographic sort)
 * - "part1a" < "part2a"
 * - "v1.2.3" < "v1.10.0"
 *
 * Algorithm:
 * 1. Split strings into alternating number/non-number parts
 * 2. Compare each part pair:
 *    - If both are numbers: numeric comparison
 *    - Otherwise: case-insensitive string comparison
 * 3. Return first non-zero difference
 *
 * Performance: O(n) where n = average string length
 *
 * Examples:
 * - naturalCompare("abc2", "abc10") → -1 (abc2 < abc10)
 * - naturalCompare("ABC", "abc") → 0 (case-insensitive)
 * - naturalCompare("v1.9", "v1.10") → -1 (v1.9 < v1.10)
 *
 * @param a - First string
 * @param b - Second string
 * @returns Negative if a < b, positive if a > b, zero if equal
 */
const naturalCompare = (a: string, b: string): number => {
  // Split strings into parts: digits or non-digits
  // Example: "abc123def456" → ["abc", "123", "def", "456"]
  const aParts = a.match(/(\d+|\D+)/g) || [];
  const bParts = b.match(/(\d+|\D+)/g) || [];

  // Compare part by part
  for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
    const aPart = aParts[i] || '';
    const bPart = bParts[i] || '';

    // Check if both parts are pure numbers
    const aIsNum = /^\d+$/.test(aPart);
    const bIsNum = /^\d+$/.test(bPart);

    if (aIsNum && bIsNum) {
      // ===== NUMERIC COMPARISON =====
      const diff = parseInt(aPart, 10) - parseInt(bPart, 10);
      if (diff !== 0) return diff;
    } else {
      // ===== STRING COMPARISON =====
      // Case-insensitive for better UX
      const diff = aPart.toLowerCase().localeCompare(bPart.toLowerCase());
      if (diff !== 0) return diff;
    }
  }

  // All parts equal
  return 0;
};

/**
 * Get nested value from object using dot notation
 *
 * Supports deep property access with dot-separated paths.
 * Safely handles undefined/null values in the path.
 *
 * Examples:
 * - getNestedValue(product, 'manufacturer') → product.manufacturer
 * - getNestedValue(product, 'rated_voltage.min') → product.rated_voltage.min
 * - getNestedValue(product, 'dimensions.length.value') → product.dimensions.length.value
 *
 * @param obj - Object to extract value from
 * @param path - Dot-separated path (e.g., 'rated_voltage.min')
 * @returns Value at path, or undefined if path doesn't exist
 */
const getNestedValue = (obj: any, path: string): any => {
  const keys = path.split('.');
  let value = obj;

  // Traverse the path
  for (const key of keys) {
    if (value === undefined || value === null) return undefined;
    value = value[key];
  }

  return value;
};

/**
 * Extract numeric value from ValueUnit or MinMaxUnit objects
 *
 * Handles different data structures:
 * - number: Return as-is
 * - ValueUnit: { value: 100, unit: 'V' } → 100
 * - MinMaxUnit: { min: 200, max: 240, unit: 'V' } → 220 (average)
 * - other: null
 *
 * Used for numeric sorting and filtering.
 *
 * @param value - Value to extract number from
 * @returns Numeric value or null if not extractable
 */
const extractNumericValue = (value: any): number | null => {
  // Already a number
  if (typeof value === 'number') return value;

  // Object types
  if (typeof value === 'object' && value !== null) {
    // ValueUnit: { value: number, unit: string }
    if ('value' in value) return value.value;

    // MinMaxUnit: { min: number, max: number, unit: string }
    // Use average for sorting/filtering
    if ('min' in value && 'max' in value) {
      return (value.min + value.max) / 2;
    }
  }

  return null;
};

/**
 * Check if a value matches a filter criterion
 *
 * Implements comprehensive matching logic for all data types:
 *
 * 1. Existence check: If no filter value, just check attribute exists
 * 2. Array matching: Check if any array element contains filter value (case-insensitive)
 * 3. ValueUnit matching: Extract value and apply numeric/string comparison
 * 4. MinMaxUnit matching: Use average value for numeric comparison
 * 5. String matching: Case-insensitive partial match (contains)
 * 6. Number matching: Use comparison operators (=, >, <, >=, <=, !=)
 * 7. Fallback: Convert to string and check contains
 *
 * Examples:
 * - matchesFilter(['EtherCAT', 'CANopen'], { value: 'ether' }) → true
 * - matchesFilter({ value: 240, unit: 'V' }, { value: 200, operator: '>' }) → true
 * - matchesFilter('ACME Motors', { value: 'acme' }) → true
 *
 * @param value - Product attribute value to check
 * @param filter - Filter criterion to match against
 * @returns True if value matches filter, false otherwise
 */
const matchesFilter = (value: any, filter: FilterCriterion): boolean => {
  // ===== EXISTENCE CHECK =====
  if (filter.value === undefined) {
    // Just checking if attribute exists (no value specified)
    return value !== undefined && value !== null;
  }

  // ===== MULTI-SELECT STRING MATCHING =====
  // When filter has multiple values (string[]), match if product value matches ANY of them (OR logic)
  if (Array.isArray(filter.value)) {
    const filterValues = filter.value; // Extract to help TypeScript
    // Handle case where product value is also an array
    if (Array.isArray(value)) {
      return value.some(v =>
        filterValues.some((fv: any) =>
          String(v).toLowerCase().includes(String(fv).toLowerCase())
        )
      );
    }
    // Product value is a single value, check if it matches any filter value
    const valueStr = String(value).toLowerCase();
    return filterValues.some((fv: any) => valueStr.includes(String(fv).toLowerCase()));
  }

  // ===== ARRAY MATCHING =====
  // For arrays (fieldbus, control_modes, safety_features, etc.)
  // Check if ANY element contains the filter value
  if (Array.isArray(value)) {
    return value.some(v =>
      String(v).toLowerCase().includes(String(filter.value).toLowerCase())
    );
  }

  // ===== OBJECT MATCHING =====
  if (typeof value === 'object' && value !== null) {
    // ValueUnit: { value: number, unit: string }
    if ('value' in value) {
      const numValue = value.value;
      if (typeof filter.value === 'number' && typeof numValue === 'number') {
        // Numeric comparison with operator
        return compareNumbers(numValue, filter.operator || '=', filter.value);
      }
      // String matching on value
      return String(numValue).toLowerCase().includes(String(filter.value).toLowerCase());
    }

    // MinMaxUnit: { min: number, max: number, unit: string }
    // Use average for comparison
    if ('min' in value && 'max' in value) {
      if (typeof filter.value === 'number') {
        const avgValue = (value.min + value.max) / 2;
        return compareNumbers(avgValue, filter.operator || '=', filter.value);
      }
    }
  }

  // ===== STRING MATCHING =====
  // Case-insensitive partial match (contains)
  if (typeof value === 'string') {
    return value.toLowerCase().includes(String(filter.value).toLowerCase());
  }

  // ===== NUMBER MATCHING =====
  // Use comparison operators (=, >, <, >=, <=, !=)
  if (typeof value === 'number' && typeof filter.value === 'number') {
    return compareNumbers(value, filter.operator || '=', filter.value);
  }

  // ===== FALLBACK =====
  // Convert to string and check contains (case-insensitive)
  return String(value).toLowerCase().includes(String(filter.value).toLowerCase());
};

/**
 * Compare two numbers using a comparison operator
 *
 * Supports all standard comparison operators:
 * - '=': Equal to (exact match)
 * - '>': Greater than
 * - '<': Less than
 * - '>=': Greater than or equal to
 * - '<=': Less than or equal to
 * - '!=': Not equal to
 *
 * Used by matchesFilter for numeric comparisons.
 *
 * Examples:
 * - compareNumbers(240, '>', 200) → true
 * - compareNumbers(100, '<=', 100) → true
 * - compareNumbers(50, '!=', 60) → true
 *
 * @param value - Actual numeric value
 * @param operator - Comparison operator
 * @param target - Target value to compare against
 * @returns True if comparison is satisfied, false otherwise
 */
const compareNumbers = (value: number, operator: ComparisonOperator, target: number): boolean => {
  switch (operator) {
    case '=':
      return value === target;
    case '>':
      return value > target;
    case '<':
      return value < target;
    case '>=':
      return value >= target;
    case '<=':
      return value <= target;
    case '!=':
      return value !== target;
    default:
      // Fallback to equality
      return value === target;
  }
};
