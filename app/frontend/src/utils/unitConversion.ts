/**
 * Display-time metric ↔ imperial unit conversion.
 *
 * The store stays canonical metric. This module is a pure display-layer
 * transformation: take a `{value, unit}` or `{min, max, unit}` object out
 * of React state, return the same shape with the value converted and the
 * unit string replaced. Filters, sort comparators, and bucketing all keep
 * working against canonical numeric values — only the rendered text and
 * the displayed unit change.
 *
 * Compound units (V/krpm, Nm/A, Nm/arcmin, Nm/√A) are coefficients, not
 * human-facing readouts. Flipping half of the unit would mislead more
 * than help; they pass through unchanged.
 *
 * Quantities with no idiomatic imperial form (V, A, Ω, mH, rpm, Hz, %,
 * arcmin, hours, IP rating, dB(A)) also pass through unchanged.
 */

export type UnitSystem = 'metric' | 'imperial';

interface UnitConversion {
  target: string;
  forward: (n: number) => number;
  inverse: (n: number) => number;
}

// Keyed by canonical metric unit string as it appears in
// AttributeMetadata.unit and in the value-unit objects coming back
// from the API.
export const IMPERIAL_CONVERSIONS: Record<string, UnitConversion> = {
  N: {
    target: 'lbf',
    forward: n => n * 0.2248089,
    inverse: n => n / 0.2248089,
  },
  Nm: {
    target: 'in·lb',
    forward: n => n * 8.850746,
    inverse: n => n / 8.850746,
  },
  kg: {
    target: 'lb',
    forward: n => n * 2.204623,
    inverse: n => n / 2.204623,
  },
  mm: {
    target: 'in',
    forward: n => n * 0.0393701,
    inverse: n => n / 0.0393701,
  },
  '°C': {
    target: '°F',
    forward: n => (n * 9) / 5 + 32,
    inverse: n => ((n - 32) * 5) / 9,
  },
  'kg·cm²': {
    target: 'oz·in²',
    forward: n => n * 13.8874,
    inverse: n => n / 13.8874,
  },
  'm/s': {
    target: 'ft/s',
    forward: n => n * 3.28084,
    inverse: n => n / 3.28084,
  },
  bar: {
    target: 'psi',
    forward: n => n * 14.50377,
    inverse: n => n / 14.50377,
  },
};

/**
 * Round a converted number to ~4 significant figures and strip trailing
 * zeros. Mirrors `_round_converted` from datasheetminer/units.py but
 * tuned for display (4 sig figs vs 6 for storage).
 */
function roundDisplay(value: number): number {
  if (!Number.isFinite(value)) return value;
  if (value === 0) return 0;
  const magnitude = Math.floor(Math.log10(Math.abs(value)));
  const precision = Math.max(0, 3 - magnitude);
  const factor = Math.pow(10, precision);
  return Math.round(value * factor) / factor;
}

/**
 * Try to parse a value as a number. Returns null if it's not parseable
 * (e.g. "~5", "approx 10"). Caller decides whether to fall back to
 * passing the input through as-is.
 */
function tryParseNumber(value: number | string): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (trimmed === '') return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
}

/**
 * Convert a single { value, unit } pair into the active display system.
 * If the unit isn't in the conversion table, or the value isn't numeric,
 * the unit is replaced (when applicable) but the value passes through —
 * better to mis-label than to crash.
 */
export function convertValueUnit<V extends number | string>(
  vu: { value: V; unit: string },
  system: UnitSystem,
): { value: V | number; unit: string } {
  if (system === 'metric') return vu;
  const conv = IMPERIAL_CONVERSIONS[vu.unit];
  if (!conv) return vu;
  const parsed = tryParseNumber(vu.value);
  if (parsed === null) {
    return { value: vu.value, unit: conv.target };
  }
  return { value: roundDisplay(conv.forward(parsed)), unit: conv.target };
}

/**
 * Convert a { min, max, unit } range into the active display system.
 * Preserves min ≤ max ordering by sorting after conversion (temperature
 * is monotonic, but this is cheap insurance for any future non-monotonic
 * conversion).
 */
export function convertMinMaxUnit<V extends number | string>(
  mmu: { min: V; max: V; unit: string },
  system: UnitSystem,
): { min: V | number; max: V | number; unit: string } {
  if (system === 'metric') return mmu;
  const conv = IMPERIAL_CONVERSIONS[mmu.unit];
  if (!conv) return mmu;
  const minN = tryParseNumber(mmu.min);
  const maxN = tryParseNumber(mmu.max);
  if (minN === null || maxN === null) {
    return {
      min: minN === null ? mmu.min : roundDisplay(conv.forward(minN)),
      max: maxN === null ? mmu.max : roundDisplay(conv.forward(maxN)),
      unit: conv.target,
    };
  }
  let lo = roundDisplay(conv.forward(minN));
  let hi = roundDisplay(conv.forward(maxN));
  if (lo > hi) [lo, hi] = [hi, lo];
  return { min: lo, max: hi, unit: conv.target };
}

/**
 * Inverse direction: a number typed by the user in the active display
 * system, converted back into canonical metric for filter state.
 *
 * `displayUnit` is the canonical metric unit that the field is keyed by
 * (e.g. "Nm" for a torque filter). When the system is imperial, the user
 * actually typed an imperial number in the imperial target unit — this
 * function reverses that to canonical.
 */
export function toCanonical(
  value: number,
  canonicalUnit: string,
  system: UnitSystem,
): number {
  if (system === 'metric') return value;
  const conv = IMPERIAL_CONVERSIONS[canonicalUnit];
  if (!conv) return value;
  return conv.inverse(value);
}

/**
 * Forward direction without an object wrapper: convert a canonical
 * numeric value into its display number. Used by chart axes and
 * column slider min/max bounds.
 */
export function toDisplay(
  value: number,
  canonicalUnit: string,
  system: UnitSystem,
): number {
  if (system === 'metric') return value;
  const conv = IMPERIAL_CONVERSIONS[canonicalUnit];
  if (!conv) return value;
  return roundDisplay(conv.forward(value));
}

/**
 * Resolve the unit string we should *show* for a given canonical unit
 * under the active system. Used by ProductList column headers and
 * filter chip labels where unit is rendered separately from value.
 */
export function displayUnit(canonicalUnit: string, system: UnitSystem): string {
  if (system === 'metric') return canonicalUnit;
  return IMPERIAL_CONVERSIONS[canonicalUnit]?.target ?? canonicalUnit;
}
