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
