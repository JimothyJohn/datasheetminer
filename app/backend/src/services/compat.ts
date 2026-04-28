/**
 * Pairwise compatibility between two products in the rotary motion chain.
 *
 * TS port of `specodex/integration/compat.py` (drive↔motor and
 * motor↔gearhead junctions only).
 *
 * Two modes:
 *   - `check(a, b)` returns the strict report — `ok`, `partial` (missing
 *     data), or `fail` (data present, mismatched). Used by client code that
 *     needs to filter or rank candidates.
 *   - `softenReport(r)` downgrades every `fail` to `partial` while keeping
 *     per-field detail. Used at the API edge so the UI never shows a hard
 *     red gate while shared schemas (fieldbus protocols, encoder names)
 *     are still being normalised.
 *
 * The Python engine remains the source of truth for stricter checks once
 * those shared enums land.
 */
import { Drive, Gearhead, MinMaxUnit, Motor, Product, ValueUnit } from '../types/models';

export type StrictStatus = 'ok' | 'partial' | 'fail';
export type SoftStatus = 'ok' | 'partial';

export interface CheckResult {
  field: string;
  status: StrictStatus;
  detail: string;
}

export interface CompatResult {
  from_port: string;
  to_port: string;
  status: StrictStatus;
  checks: CheckResult[];
}

export interface CompatibilityReport {
  from_type: string;
  to_type: string;
  status: StrictStatus;
  results: CompatResult[];
}

export interface SoftCheckResult {
  field: string;
  status: SoftStatus;
  detail: string;
}

export interface SoftCompatResult {
  from_port: string;
  to_port: string;
  status: SoftStatus;
  checks: SoftCheckResult[];
}

export interface SoftCompatibilityReport {
  from_type: string;
  to_type: string;
  status: SoftStatus;
  results: SoftCompatResult[];
}

const isMinMaxUnit = (v: unknown): v is MinMaxUnit =>
  !!v && typeof v === 'object' && 'min' in (v as object) && 'max' in (v as object) && 'unit' in (v as object);

const ok = (field: string, detail: string): CheckResult => ({ field, status: 'ok', detail });
const partial = (field: string, detail: string): CheckResult => ({ field, status: 'partial', detail });
const fail = (field: string, detail: string): CheckResult => ({ field, status: 'fail', detail });

function rollUp(checks: { status: StrictStatus }[]): StrictStatus {
  if (checks.some(c => c.status === 'fail')) return 'fail';
  if (checks.some(c => c.status === 'partial')) return 'partial';
  return 'ok';
}

// ---------------------------------------------------------------------------
// Field-level comparators
//
// `partial` = at least one side missing the field (can't prove anything).
// `fail`    = both sides have data and the data disagrees.
// ---------------------------------------------------------------------------

function checkVoltageFits(supply: MinMaxUnit | undefined, demand: MinMaxUnit | ValueUnit | undefined): CheckResult {
  if (!supply || !demand) return partial('voltage', 'one side missing voltage');
  const dMin = isMinMaxUnit(demand) ? demand.min : demand.value;
  const dMax = isMinMaxUnit(demand) ? demand.max : demand.value;
  const dUnit = demand.unit;
  if (supply.unit !== dUnit) return fail('voltage', `unit mismatch: ${supply.unit} vs ${dUnit}`);
  if (dMin < supply.min || dMax > supply.max) {
    return fail('voltage', `demand ${dMin}-${dMax} outside supply ${supply.min}-${supply.max} ${supply.unit}`);
  }
  return ok('voltage', `${dMin}-${dMax} within ${supply.min}-${supply.max} ${supply.unit}`);
}

function checkSupplyGeDemand(supply: ValueUnit | undefined, demand: ValueUnit | undefined, field: string): CheckResult {
  if (!supply || !demand) return partial(field, `one side missing ${field}`);
  if (supply.unit !== demand.unit) return fail(field, `unit mismatch: ${supply.unit} vs ${demand.unit}`);
  if (supply.value < demand.value) {
    return fail(field, `supply ${supply.value} < demand ${demand.value} ${supply.unit}`);
  }
  return ok(field, `supply ${supply.value} ≥ demand ${demand.value} ${supply.unit}`);
}

function checkDemandLeMax(demand: ValueUnit | undefined, max: ValueUnit | undefined, field: string): CheckResult {
  return checkSupplyGeDemand(max, demand, field);
}

function checkEqualString(a: string | undefined, b: string | undefined, field: string): CheckResult {
  if (!a || !b) return partial(field, `one side missing ${field}`);
  if (a.trim().toLowerCase() !== b.trim().toLowerCase()) {
    return fail(field, `${a} != ${b}`);
  }
  return ok(field, a);
}

function checkMembership(value: string | undefined, options: string[] | undefined, field: string): CheckResult {
  if (!value || !options || options.length === 0) return partial(field, 'one side missing');
  const v = value.trim().toLowerCase();
  if (options.some(o => o.trim().toLowerCase() === v)) return ok(field, `${value} in supported list`);
  return fail(field, `${value} not in [${options.join(', ')}]`);
}

/**
 * Motor shaft OD must equal gearhead bore within 0.1 mm. Motor shafts couple
 * via keyed/clamped bores — a mismatch of any size is the wrong part.
 */
function checkShaftFit(motorShaft: ValueUnit | undefined, bore: ValueUnit | undefined): CheckResult {
  if (!motorShaft || !bore) return partial('shaft_diameter', 'one side missing');
  if (motorShaft.unit !== bore.unit) {
    return fail('shaft_diameter', `unit mismatch: ${motorShaft.unit} vs ${bore.unit}`);
  }
  if (Math.abs(motorShaft.value - bore.value) > 0.1) {
    return fail('shaft_diameter', `motor ${motorShaft.value} ${motorShaft.unit} ≠ gearhead bore ${bore.value} ${bore.unit}`);
  }
  return ok('shaft_diameter', `${motorShaft.value} ${motorShaft.unit} matches bore`);
}

// ---------------------------------------------------------------------------
// Junction comparators
// ---------------------------------------------------------------------------

function compareDriveMotorPower(drive: Drive, motor: Motor): CompatResult {
  // Drive reproduces its input voltage at the motor side via PWM; motor's
  // rated_voltage range must sit within the drive's input_voltage envelope.
  const checks: CheckResult[] = [
    checkVoltageFits(drive.input_voltage, motor.rated_voltage),
    checkSupplyGeDemand(drive.rated_current, motor.rated_current, 'current'),
    checkSupplyGeDemand(drive.rated_power, motor.rated_power, 'power'),
  ];
  return {
    from_port: 'Drive.motor_output',
    to_port: 'Motor.power_input',
    status: rollUp(checks),
    checks,
  };
}

function compareDriveMotorFeedback(drive: Drive, motor: Motor): CompatResult {
  const checks: CheckResult[] = [
    checkMembership(motor.encoder_feedback_support, drive.encoder_feedback_support, 'encoder_type'),
  ];
  return {
    from_port: 'Drive.feedback',
    to_port: 'Motor.feedback',
    status: rollUp(checks),
    checks,
  };
}

function compareMotorGearheadShaft(motor: Motor, gearhead: Gearhead): CompatResult {
  const checks: CheckResult[] = [
    checkEqualString(motor.frame_size, gearhead.frame_size, 'frame_size'),
    checkShaftFit(motor.shaft_diameter, gearhead.input_shaft_diameter),
    // Motor's `rated_speed` is the closest analogue to the Python `max_speed`;
    // the gearhead's `max_input_speed` is the ceiling.
    checkDemandLeMax(motor.rated_speed, gearhead.max_input_speed, 'speed'),
  ];
  return {
    from_port: 'Motor.shaft_output',
    to_port: 'Gearhead.shaft_input',
    status: rollUp(checks),
    checks,
  };
}

// ---------------------------------------------------------------------------
// Top-level dispatch
// ---------------------------------------------------------------------------

const SUPPORTED_PAIRS = new Set(['drive|motor', 'motor|drive', 'motor|gearhead', 'gearhead|motor']);

function pairKey(a: Product, b: Product): string {
  return `${a.product_type}|${b.product_type}`;
}

export function isPairSupported(aType: string, bType: string): boolean {
  return SUPPORTED_PAIRS.has(`${aType}|${bType}`);
}

/**
 * Adjacent product types in the rotary chain. Used by the UI to scope the
 * "check against another" picker and the build tray's filter.
 */
export const ADJACENT_TYPES: Record<string, string[]> = {
  drive: ['motor'],
  motor: ['drive', 'gearhead'],
  gearhead: ['motor'],
};

/**
 * Strict pairwise compatibility check. Status is `ok` | `partial` | `fail`.
 * Throws if the pair isn't one of the supported rotary junctions.
 */
export function check(a: Product, b: Product): CompatibilityReport {
  const key = pairKey(a, b);
  if (!SUPPORTED_PAIRS.has(key)) {
    throw new Error(`Unsupported product pair: ${a.product_type} + ${b.product_type}`);
  }

  // Normalise so the higher-up-the-chain product is `first`.
  const reverse = key === 'motor|drive' || key === 'gearhead|motor';
  const [first, second] = reverse ? [b, a] : [a, b];

  const results: CompatResult[] = [];
  if (first.product_type === 'drive' && second.product_type === 'motor') {
    results.push(compareDriveMotorPower(first as Drive, second as Motor));
    results.push(compareDriveMotorFeedback(first as Drive, second as Motor));
  } else if (first.product_type === 'motor' && second.product_type === 'gearhead') {
    results.push(compareMotorGearheadShaft(first as Motor, second as Gearhead));
  }

  return {
    from_type: first.product_type,
    to_type: second.product_type,
    status: results.length === 0 ? 'partial' : rollUp(results),
    results,
  };
}

/**
 * Downgrade every `fail` to `partial` for display. Detail strings are
 * preserved verbatim so the UI can still surface what didn't match.
 */
export function softenReport(report: CompatibilityReport): SoftCompatibilityReport {
  const softResults: SoftCompatResult[] = report.results.map(r => {
    const checks: SoftCheckResult[] = r.checks.map(c => ({
      field: c.field,
      status: c.status === 'fail' ? 'partial' : c.status,
      detail: c.detail,
    }));
    const status: SoftStatus = checks.some(c => c.status === 'partial') ? 'partial' : 'ok';
    return { from_port: r.from_port, to_port: r.to_port, status, checks };
  });
  const overall: SoftStatus = softResults.length === 0 ? 'partial'
    : softResults.some(r => r.status === 'partial') ? 'partial' : 'ok';
  return {
    from_type: report.from_type,
    to_type: report.to_type,
    status: overall,
    results: softResults,
  };
}
