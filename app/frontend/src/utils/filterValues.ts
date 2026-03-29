/**
 * Utilities for extracting and managing filter values from products
 */

import { Product } from '../types/models';

/**
 * Extract unique values for a given attribute from products
 */
export function extractUniqueValues(
  products: Product[],
  attribute: string,
  limit: number = 20
): Array<string | number> {
  const values = new Set<string | number>();

  products.forEach(product => {
    const value = getNestedValue(product, attribute);

    if (value === undefined || value === null) return;

    // Handle arrays (e.g., fieldbus, control_modes)
    if (Array.isArray(value)) {
      value.forEach(v => {
        if (v !== undefined && v !== null) {
          values.add(String(v));
        }
      });
      return;
    }

    // Handle objects (ValueUnit, MinMaxUnit)
    if (typeof value === 'object') {
      if ('value' in value && value.value !== undefined) {
        // ValueUnit - extract the numeric value
        values.add(value.value);
      } else if ('min' in value && 'max' in value) {
        // MinMaxUnit - extract both min and max
        if (value.min !== undefined) values.add(value.min);
        if (value.max !== undefined) values.add(value.max);
      }
      return;
    }

    // Handle primitive values
    if (typeof value === 'string' || typeof value === 'number') {
      values.add(value);
    }
  });

  // Convert to array and sort
  const sortedValues = Array.from(values).sort((a, b) => {
    // Sort numbers numerically, strings alphabetically
    if (typeof a === 'number' && typeof b === 'number') {
      return a - b;
    }
    return String(a).localeCompare(String(b));
  });

  // Return top N values
  return sortedValues.slice(0, limit);
}

/**
 * Get nested value from object using dot notation
 */
function getNestedValue(obj: any, path: string): any {
  const keys = path.split('.');
  let value = obj;

  for (const key of keys) {
    if (value === undefined || value === null) return undefined;
    value = value[key];
  }

  return value;
}

/**
 * Extract a numeric value from a product attribute, traversing dot-notation paths.
 * Handles: bare numbers, ValueUnit (.value), MinMaxUnit (avg of min/max),
 * and legacy shapes (.nominal, .rated).
 */
export function extractNumeric(product: any, attribute: string): number | null {
  const val = getNestedValue(product, attribute);
  return numericFromValue(val);
}

/**
 * Extract a numeric value from a resolved value (no path traversal).
 * Shared core for sorting, filtering, proximity coloring, and auto-gear.
 */
export function numericFromValue(val: any): number | null {
  if (val == null) return null;
  if (typeof val === 'number') return val;
  if (typeof val === 'object') {
    if ('value' in val && typeof val.value === 'number') return val.value;
    if ('nominal' in val && typeof val.nominal === 'number') return val.nominal;
    if ('rated' in val && typeof val.rated === 'number') return val.rated;
    const hasMin = 'min' in val && val.min != null;
    const hasMax = 'max' in val && val.max != null;
    if (hasMin && hasMax) return (Number(val.min) + Number(val.max)) / 2;
    if (hasMin) return Number(val.min);
    if (hasMax) return Number(val.max);
  }
  return null;
}

/**
 * Format a value for display
 */
export function formatValueForDisplay(value: string | number): string {
  if (typeof value === 'number') {
    // Format numbers with appropriate precision
    if (Number.isInteger(value)) {
      return value.toString();
    }
    // Show up to 2 decimal places for floats
    return value.toFixed(2).replace(/\.?0+$/, '');
  }
  return String(value);
}
