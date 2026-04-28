// =============================================================================
//
//                    >>>  EDIT THIS FILE TO REORDER COLUMNS  <<<
//
//   Single source of truth for the order of columns in the results table.
//   Every visitor sees exactly this order — there is intentionally NO
//   per-user override and NO admin UI.
//
//   How to use:
//     1. Find the product type below (motor, drive, contactor, ...).
//     2. Edit its array — keys appear in the table left-to-right in this order.
//     3. Save. The dev server hot-reloads. Ship via the usual deploy.
//
//   What the keys are:
//     They're the snake_case attribute keys from the product schemas in
//     datasheetminer/models/<type>.py — same keys the API returns.
//     E.g. for motors: 'rated_power', 'rated_torque', 'rated_speed', ...
//     Look at app/frontend/src/types/filters.ts (getMotorAttributes etc.)
//     for the full list per type.
//
//   What happens to keys you DON'T list:
//     They fall through to alphabetical at the end of the row, so a new
//     field added to a schema never silently disappears — you just see it
//     trailing the authored columns until you decide where it belongs.
//
//   `part_number` is pinned as the leading column by ProductList.tsx and
//   is excluded from this list — don't put it here.
//
// =============================================================================

import type { ProductType } from './models';
import type { AttributeMetadata } from './filters';

export const COLUMN_ORDER: Partial<
  Record<Exclude<ProductType, null | 'all'>, string[]>
> = {
  motor: [
    'rated_power',
    'rated_torque',
    'rated_speed',
    'rated_voltage',
    'rated_current',
  ],
  drive: [
    'rated_power',
    'input_voltage',
    'input_voltage_phases',
    'rated_current',
    'peak_current',
  ],
  robot_arm: [
    // e.g. 'manufacturer', 'payload', 'reach', 'degrees_of_freedom', 'pose_repeatability', 'max_tcp_speed',
  ],
  gearhead: [
    // e.g. 'manufacturer', 'gear_ratio', 'gear_type', 'rated_torque', 'peak_torque', 'backlash', 'efficiency',
  ],
  contactor: [
    // e.g. 'manufacturer', 'ie_ac3_400v', 'motor_power_ac3_400v_kw', 'motor_power_ac3_480v_hp',
  ],
  electric_cylinder: [
    // e.g. 'manufacturer', 'stroke', 'max_push_force', 'continuous_force', 'max_linear_speed', 'rated_voltage',
  ],
  datasheet: [
    // e.g. 'manufacturer', 'product_name', 'product_family', 'component_type',
  ],
};

/**
 * Order attributes for table rendering: authored COLUMN_ORDER keys first
 * (in declared order), then unlisted keys alphabetical by displayName.
 */
export const orderColumnAttributes = (
  attrs: AttributeMetadata[],
  productType: ProductType,
): AttributeMetadata[] => {
  const order =
    productType && productType !== 'all'
      ? COLUMN_ORDER[productType] ?? []
      : [];
  const indexOf = new Map(order.map((k, i) => [k, i] as const));
  return [...attrs].sort((a, b) => {
    const ai = indexOf.get(a.key);
    const bi = indexOf.get(b.key);
    if (ai !== undefined && bi !== undefined) return ai - bi;
    if (ai !== undefined) return -1;
    if (bi !== undefined) return 1;
    return a.displayName.localeCompare(b.displayName);
  });
};
