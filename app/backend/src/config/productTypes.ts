/**
 * Product Types Configuration
 *
 * This file defines all valid product types that the system supports.
 * It should be kept in sync with the Python schemas in datasheetminer/models/
 *
 * To add a new product type:
 * 1. Create a new Pydantic model in datasheetminer/models/your_type.py
 * 2. Add the type to this array
 * 3. The system will automatically discover and display it
 */

/**
 * All valid product types in the system
 * These correspond to Pydantic model files in datasheetminer/models/
 */
export const VALID_PRODUCT_TYPES = [
  'motor',
  'drive',
  'gearhead',
  'robot_arm',
] as const;

/**
 * Type helper for valid product types
 */
export type ValidProductType = typeof VALID_PRODUCT_TYPES[number];

/**
 * Format a product type as a display name
 * Examples: "motor" -> "Motors", "robot_arm" -> "Robot Arms"
 */
export function formatDisplayName(type: string): string {
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ') + 's';
}
