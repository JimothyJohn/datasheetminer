/**
 * Filter types for advanced product filtering
 */

import { Product } from './models';

/**
 * Filter mode: include (must have), exclude (must not have), or neutral (ignored)
 */
export type FilterMode = 'include' | 'exclude' | 'neutral';

/**
 * Comparison operator for numeric filters
 */
export type ComparisonOperator = '=' | '>' | '<' | '>=' | '<=' | '!=';

/**
 * Value type for a filter
 */
export type FilterValue = string | number | boolean | [number, number];

/**
 * A single filter criterion
 */
export interface FilterCriterion {
  attribute: string;
  mode: FilterMode;
  value?: FilterValue;
  operator?: ComparisonOperator;
  displayName: string;
}

/**
 * Sort configuration
 */
export interface SortConfig {
  attribute: string;
  direction: 'asc' | 'desc';
  displayName: string;
}

/**
 * Attribute metadata for UI display
 */
export interface AttributeMetadata {
  key: string;
  displayName: string;
  type: 'string' | 'number' | 'boolean' | 'range' | 'array' | 'object';
  applicableTypes: ('motor' | 'drive')[];
  nested?: boolean; // For ValueUnit and MinMaxUnit types
}

/**
 * Get all filterable attributes for motors
 */
export const getMotorAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['motor'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['motor'] },
  { key: 'type', displayName: 'Motor Type', type: 'string', applicableTypes: ['motor'] },
  { key: 'series', displayName: 'Series', type: 'string', applicableTypes: ['motor'] },
  { key: 'rated_voltage', displayName: 'Rated Voltage', type: 'range', applicableTypes: ['motor'], nested: true },
  { key: 'rated_speed', displayName: 'Rated Speed', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'rated_torque', displayName: 'Rated Torque', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'peak_torque', displayName: 'Peak Torque', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'rated_power', displayName: 'Rated Power', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'encoder_feedback_support', displayName: 'Encoder Feedback', type: 'string', applicableTypes: ['motor'] },
  { key: 'poles', displayName: 'Poles', type: 'number', applicableTypes: ['motor'] },
  { key: 'rated_current', displayName: 'Rated Current', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'peak_current', displayName: 'Peak Current', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'voltage_constant', displayName: 'Voltage Constant', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'torque_constant', displayName: 'Torque Constant', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'resistance', displayName: 'Resistance', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'inductance', displayName: 'Inductance', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'ip_rating', displayName: 'IP Rating', type: 'number', applicableTypes: ['motor'] },
  { key: 'rotor_inertia', displayName: 'Rotor Inertia', type: 'object', applicableTypes: ['motor'], nested: true },
  { key: 'weight', displayName: 'Weight', type: 'object', applicableTypes: ['motor'], nested: true },
];

/**
 * Get all filterable attributes for drives
 */
export const getDriveAttributes = (): AttributeMetadata[] => [
  { key: 'manufacturer', displayName: 'Manufacturer', type: 'string', applicableTypes: ['drive'] },
  { key: 'part_number', displayName: 'Part Number', type: 'string', applicableTypes: ['drive'] },
  { key: 'type', displayName: 'Drive Type', type: 'string', applicableTypes: ['drive'] },
  { key: 'series', displayName: 'Series', type: 'string', applicableTypes: ['drive'] },
  { key: 'input_voltage', displayName: 'Input Voltage', type: 'range', applicableTypes: ['drive'], nested: true },
  { key: 'input_voltage_phases', displayName: 'Input Voltage Phases', type: 'array', applicableTypes: ['drive'] },
  { key: 'rated_current', displayName: 'Rated Current', type: 'object', applicableTypes: ['drive'], nested: true },
  { key: 'peak_current', displayName: 'Peak Current', type: 'object', applicableTypes: ['drive'], nested: true },
  { key: 'output_power', displayName: 'Output Power', type: 'object', applicableTypes: ['drive'], nested: true },
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
  { key: 'max_humidity', displayName: 'Max Humidity', type: 'number', applicableTypes: ['drive'] },
  { key: 'ip_rating', displayName: 'IP Rating', type: 'number', applicableTypes: ['drive'] },
  { key: 'ambient_temp', displayName: 'Ambient Temperature', type: 'range', applicableTypes: ['drive'], nested: true },
  { key: 'weight', displayName: 'Weight', type: 'object', applicableTypes: ['drive'], nested: true },
];

/**
 * Get all attributes for a specific product type
 */
export const getAttributesForType = (productType: 'motor' | 'drive' | 'all'): AttributeMetadata[] => {
  if (productType === 'motor') return getMotorAttributes();
  if (productType === 'drive') return getDriveAttributes();

  // For 'all', return common attributes
  const motorAttrs = getMotorAttributes();
  const driveAttrs = getDriveAttributes();
  const commonKeys = new Set<string>();
  const commonAttrs: AttributeMetadata[] = [];

  motorAttrs.forEach(attr => {
    const driveAttr = driveAttrs.find(d => d.key === attr.key);
    if (driveAttr && !commonKeys.has(attr.key)) {
      commonKeys.add(attr.key);
      commonAttrs.push({
        ...attr,
        applicableTypes: ['motor', 'drive']
      });
    }
  });

  return commonAttrs;
};

/**
 * Apply filters to products (client-side filtering)
 */
export const applyFilters = (products: Product[], filters: FilterCriterion[]): Product[] => {
  return products.filter(product => {
    // Check each filter criterion
    for (const filter of filters) {
      if (filter.mode === 'neutral') continue;

      const value = getNestedValue(product, filter.attribute);

      // If attribute doesn't exist, skip this product for 'include' mode
      if (value === undefined || value === null) {
        if (filter.mode === 'include') return false;
        continue;
      }

      const matches = matchesFilter(value, filter);

      if (filter.mode === 'include' && !matches) return false;
      if (filter.mode === 'exclude' && matches) return false;
    }

    return true;
  });
};

/**
 * Sort products by multiple attributes with natural alphanumeric sorting
 * Supports multi-level sorting: first by sorts[0], then sorts[1], etc.
 */
export const sortProducts = (products: Product[], sort: SortConfig | SortConfig[] | null): Product[] => {
  if (!sort) return products;

  // Convert single sort to array for uniform handling
  const sorts = Array.isArray(sort) ? sort : [sort];
  if (sorts.length === 0) return products;

  return [...products].sort((a, b) => {
    // Try each sort level until we find a difference
    for (const sortConfig of sorts) {
      const aVal = getNestedValue(a, sortConfig.attribute);
      const bVal = getNestedValue(b, sortConfig.attribute);

      // Handle null/undefined
      if (aVal === undefined || aVal === null) {
        if (bVal === undefined || bVal === null) continue; // Both null, try next sort
        return 1; // a is null, b is not, a goes after
      }
      if (bVal === undefined || bVal === null) return -1; // b is null, a is not, a goes before

      // Extract numeric values from ValueUnit or MinMaxUnit
      const aNum = extractNumericValue(aVal);
      const bNum = extractNumericValue(bVal);

      let comparison = 0;
      if (typeof aNum === 'number' && typeof bNum === 'number') {
        // Pure numeric comparison
        comparison = aNum - bNum;
      } else {
        // Use natural alphanumeric sorting (treats embedded numbers naturally)
        comparison = naturalCompare(String(aVal), String(bVal));
      }

      // Apply direction
      comparison = sortConfig.direction === 'asc' ? comparison : -comparison;

      // If we found a difference, return it
      if (comparison !== 0) return comparison;

      // If equal, continue to next sort level
    }

    // All sort levels equal
    return 0;
  });
};

/**
 * Natural alphanumeric comparison
 * Handles strings with embedded numbers properly (e.g., "abc10" > "abc2")
 */
const naturalCompare = (a: string, b: string): number => {
  // Split strings into parts of letters and numbers
  const aParts = a.match(/(\d+|\D+)/g) || [];
  const bParts = b.match(/(\d+|\D+)/g) || [];

  for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
    const aPart = aParts[i] || '';
    const bPart = bParts[i] || '';

    // Check if both parts are numbers
    const aIsNum = /^\d+$/.test(aPart);
    const bIsNum = /^\d+$/.test(bPart);

    if (aIsNum && bIsNum) {
      // Compare as numbers
      const diff = parseInt(aPart, 10) - parseInt(bPart, 10);
      if (diff !== 0) return diff;
    } else {
      // Compare as strings (case-insensitive)
      const diff = aPart.toLowerCase().localeCompare(bPart.toLowerCase());
      if (diff !== 0) return diff;
    }
  }

  return 0;
};

/**
 * Get nested value from object using dot notation
 */
const getNestedValue = (obj: any, path: string): any => {
  const keys = path.split('.');
  let value = obj;

  for (const key of keys) {
    if (value === undefined || value === null) return undefined;
    value = value[key];
  }

  return value;
};

/**
 * Extract numeric value from ValueUnit or MinMaxUnit
 */
const extractNumericValue = (value: any): number | null => {
  if (typeof value === 'number') return value;
  if (typeof value === 'object') {
    if ('value' in value) return value.value;
    if ('min' in value && 'max' in value) return (value.min + value.max) / 2;
  }
  return null;
};

/**
 * Check if a value matches a filter criterion
 */
const matchesFilter = (value: any, filter: FilterCriterion): boolean => {
  if (filter.value === undefined) {
    // Just checking for existence
    return value !== undefined && value !== null;
  }

  // Handle arrays (e.g., fieldbus, control_modes)
  if (Array.isArray(value)) {
    return value.some(v =>
      String(v).toLowerCase().includes(String(filter.value).toLowerCase())
    );
  }

  // Handle objects (ValueUnit, MinMaxUnit)
  if (typeof value === 'object' && value !== null) {
    if ('value' in value) {
      // ValueUnit
      const numValue = value.value;
      if (typeof filter.value === 'number' && typeof numValue === 'number') {
        return compareNumbers(numValue, filter.operator || '=', filter.value);
      }
      return String(numValue).toLowerCase().includes(String(filter.value).toLowerCase());
    }
    if ('min' in value && 'max' in value) {
      // MinMaxUnit - use average for comparison
      if (typeof filter.value === 'number') {
        const avgValue = (value.min + value.max) / 2;
        return compareNumbers(avgValue, filter.operator || '=', filter.value);
      }
    }
  }

  // Handle strings
  if (typeof value === 'string') {
    return value.toLowerCase().includes(String(filter.value).toLowerCase());
  }

  // Handle numbers with comparison operators
  if (typeof value === 'number' && typeof filter.value === 'number') {
    return compareNumbers(value, filter.operator || '=', filter.value);
  }

  return String(value).toLowerCase().includes(String(filter.value).toLowerCase());
};

/**
 * Compare two numbers using a comparison operator
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
      return value === target;
  }
};
