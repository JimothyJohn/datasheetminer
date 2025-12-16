/**
 * Formatting utilities for displaying product properties
 */

/**
 * Format a snake_case property key into a properly capitalized label
 *
 * Handles common acronyms that should be fully capitalized (IP, AC, DC, etc.)
 * and converts snake_case to Title Case for regular words.
 *
 * Examples:
 * - formatPropertyLabel('ip_rating') → 'IP Rating'
 * - formatPropertyLabel('rated_voltage') → 'Rated Voltage'
 * - formatPropertyLabel('ac_input') → 'AC Input'
 * - formatPropertyLabel('pwm_frequency') → 'PWM Frequency'
 *
 * @param key - Snake_case property key
 * @returns Properly formatted display label
 */
export const formatPropertyLabel = (key: string): string => {
  // Common acronyms that should be fully capitalized
  const acronyms = new Set([
    'ip', 'ac', 'dc', 'pwm', 'rpm', 'emf', 'rms', 'led', 'usb', 'io',
    'api', 'url', 'id', 'can', 'uart', 'spi', 'i2c', 'nema', 'iec',
    'din', 'ansi', 'iso', 'ul', 'ce', 'fcc', 'rohs', 'pid', 'plc',
    'hmi', 'vfd', 'hp', 'kw', 'fps', 'dpi', 'psi', 'gpm', 'cfm'
  ]);

  return key
    .split('_')
    .map(word => {
      const lowerWord = word.toLowerCase();
      // If it's an acronym, uppercase the entire word
      if (acronyms.has(lowerWord)) {
        return word.toUpperCase();
      }
      // Otherwise, capitalize first letter only
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
};

/**
 * Recursively format a value for display, handling nested objects and arrays
 *
 * Handles common patterns:
 * - Primitives (strings, numbers, booleans)
 * - null/undefined → 'N/A'
 * - Arrays → comma-separated values
 * - Objects with value+unit → "value unit"
 * - Objects with min+max+unit → "min-max unit"
 * - Objects with nominal+unit → "nominal unit"
 * - Objects with rated+unit → "rated unit"
 * - Nested objects → formatted key-value pairs
 *
 * @param value - The value to format
 * @param depth - Current recursion depth (prevents infinite recursion)
 * @param maxDepth - Maximum recursion depth (default: 5)
 * @returns Formatted string representation
 */
export const formatValue = (value: any, depth: number = 0, maxDepth: number = 5): string => {
  // Prevent infinite recursion
  if (depth > maxDepth) {
    return '[Max depth exceeded]';
  }

  // Handle null/undefined
  if (value === null || value === undefined) {
    return 'N/A';
  }

  // Handle primitives
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  // Handle arrays
  if (Array.isArray(value)) {
    if (value.length === 0) return 'N/A';

    // Check if array contains objects with value/unit pattern
    if (value.length > 0 && typeof value[0] === 'object' && value[0] !== null) {
      if ('value' in value[0] && 'unit' in value[0]) {
        const formattedValues = value.map(item => String(item.value)).join(', ');
        const commonUnit = value[0].unit;
        return `${formattedValues} ${commonUnit}`;
      }
      
      // Check if array contains objects with min/max/unit pattern
      if ('min' in value[0] && 'max' in value[0] && 'unit' in value[0]) {
         const formattedValues = value.map(item => `${item.min}-${item.max}`).join(', ');
         const commonUnit = value[0].unit;
         return `${formattedValues} ${commonUnit}`;
      }
    }

    // Otherwise, recursively format each element
    return value.map(item => formatValue(item, depth + 1, maxDepth)).join(', ');
  }

  // Handle objects
  if (typeof value === 'object') {
    // Pattern: { value, unit }
    if ('value' in value && 'unit' in value) {
      return `${value.value} ${value.unit}`;
    }

    // Pattern: { min, max, unit }
    if ('min' in value && 'max' in value && 'unit' in value) {
      return `${value.min}-${value.max} ${value.unit}`;
    }

    // Pattern: { nominal, unit }
    if ('nominal' in value && 'unit' in value) {
      return `${value.nominal} ${value.unit}`;
    }

    // Pattern: { rated, unit }
    if ('rated' in value && 'unit' in value) {
      return `${value.rated} ${value.unit}`;
    }

    // Pattern: { min, max } without unit
    if ('min' in value && 'max' in value && !('unit' in value)) {
      const otherKeys = Object.keys(value).filter(k => k !== 'min' && k !== 'max');
      if (otherKeys.length === 0) {
        return `${value.min}-${value.max}`;
      }
    }

    // Pattern: Multiple numeric properties with a common unit
    const entries = Object.entries(value);
    const unitEntry = entries.find(([key]) => key.toLowerCase() === 'unit');

    if (unitEntry) {
      const numericEntries = entries.filter(([key, val]) =>
        key.toLowerCase() !== 'unit' && typeof val === 'number'
      );

      if (numericEntries.length > 0 && numericEntries.length === entries.length - 1) {
        // All non-unit entries are numeric
        const formatted = numericEntries.map(([key, val]) =>
          `${formatPropertyLabel(key)}: ${val}`
        ).join(', ');
        return `${formatted} ${unitEntry[1]}`;
      }
    }

    // Generic nested object: format as key-value pairs
    const formattedEntries = entries
      .filter(([key]) => key.toLowerCase() !== 'unit') // Filter out standalone unit keys
      .map(([key, val]) => {
        const label = formatPropertyLabel(key);
        const formattedVal = formatValue(val, depth + 1, maxDepth);
        return `${label}: ${formattedVal}`;
      })
      .filter(entry => !entry.endsWith(': N/A')); // Filter out N/A values

    if (formattedEntries.length === 0) return 'N/A';

    // If there was a unit at this level, append it
    if (unitEntry) {
      return `${formattedEntries.join(', ')} ${unitEntry[1]}`;
    }

    return formattedEntries.join(', ');
  }

  // Fallback
  return String(value);
};
