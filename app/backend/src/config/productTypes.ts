/**
 * Product Types Configuration
 *
 * This file defines all valid product types that the system supports.
 *
 * To add a new product type:
 * 1. Add the type to this array
 * 2. Update the data models and UI components as needed
 */

/**
 * All valid product types in the system
 */
export const VALID_PRODUCT_TYPES = [
  'motor',
  'drive',
  'gearhead',
  'robot_arm',
  'datasheet',
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
