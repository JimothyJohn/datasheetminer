import { describe, it, expect } from 'vitest';
import {
  IMPERIAL_CONVERSIONS,
  convertValueUnit,
  convertMinMaxUnit,
  toCanonical,
  toDisplay,
  displayUnit,
} from './unitConversion';

describe('IMPERIAL_CONVERSIONS round-trips', () => {
  for (const [canonical, conv] of Object.entries(IMPERIAL_CONVERSIONS)) {
    it(`${canonical} → ${conv.target} → ${canonical} round-trips`, () => {
      for (const x of [0, 1, 5, 42, 100, 1234.5, -20, -40]) {
        const there = conv.forward(x);
        const back = conv.inverse(there);
        expect(back).toBeCloseTo(x, 6);
      }
    });
  }
});

describe('convertValueUnit', () => {
  it('passes through unchanged in metric mode', () => {
    expect(convertValueUnit({ value: 100, unit: 'N' }, 'metric')).toEqual({
      value: 100,
      unit: 'N',
    });
  });

  it('converts N → lbf', () => {
    const out = convertValueUnit({ value: 100, unit: 'N' }, 'imperial');
    expect(out.unit).toBe('lbf');
    expect(out.value).toBeCloseTo(22.48, 1);
  });

  it('converts Nm → in·lb', () => {
    const out = convertValueUnit({ value: 1, unit: 'Nm' }, 'imperial');
    expect(out.unit).toBe('in·lb');
    expect(out.value).toBeCloseTo(8.851, 2);
  });

  it('converts kg → lb', () => {
    const out = convertValueUnit({ value: 1.5, unit: 'kg' }, 'imperial');
    expect(out.unit).toBe('lb');
    expect(out.value).toBeCloseTo(3.307, 2);
  });

  it('converts mm → in', () => {
    const out = convertValueUnit({ value: 100, unit: 'mm' }, 'imperial');
    expect(out.unit).toBe('in');
    expect(out.value).toBeCloseTo(3.937, 2);
  });

  it('converts W → hp', () => {
    const out = convertValueUnit({ value: 745.69987, unit: 'W' }, 'imperial');
    expect(out.unit).toBe('hp');
    expect(out.value).toBeCloseTo(1, 3);
  });

  it('converts kW → hp', () => {
    const out = convertValueUnit({ value: 1, unit: 'kW' }, 'imperial');
    expect(out.unit).toBe('hp');
    expect(out.value).toBeCloseTo(1.341, 2);
  });

  it('converts °C → °F (offset, not multiplier)', () => {
    expect(convertValueUnit({ value: 0, unit: '°C' }, 'imperial').value).toBe(32);
    const minus40 = convertValueUnit({ value: -40, unit: '°C' }, 'imperial');
    expect(minus40.value).toBeCloseTo(-40, 5);
    expect(minus40.unit).toBe('°F');
    const hundred = convertValueUnit({ value: 100, unit: '°C' }, 'imperial');
    expect(hundred.value).toBe(212);
  });

  it('keeps unit unchanged for units with no imperial form (V, A, rpm)', () => {
    // Integer-display units (V, rpm) round but keep the canonical unit
    // string. Quantities like A, Ω, mH have no imperial form and aren't
    // in INTEGER_DISPLAY_UNITS — they pass through fully unchanged.
    expect(convertValueUnit({ value: 24, unit: 'V' }, 'imperial')).toEqual({
      value: 24,
      unit: 'V',
    });
    expect(convertValueUnit({ value: 3000, unit: 'rpm' }, 'imperial')).toEqual({
      value: 3000,
      unit: 'rpm',
    });
    expect(convertValueUnit({ value: 12.5, unit: 'A' }, 'imperial')).toEqual({
      value: 12.5,
      unit: 'A',
    });
  });

  it('rounds voltages to integers in both systems', () => {
    // Datasheets list voltages as 24/48/230/480 — fractional volts are
    // extraction noise. Round at display time.
    expect(convertValueUnit({ value: 3.3, unit: 'V' }, 'metric')).toEqual({
      value: 3,
      unit: 'V',
    });
    expect(convertValueUnit({ value: 230.4, unit: 'V' }, 'imperial')).toEqual({
      value: 230,
      unit: 'V',
    });
    expect(convertValueUnit({ value: 1.5, unit: 'kV' }, 'metric')).toEqual({
      value: 2,
      unit: 'kV',
    });
  });

  it('rounds rpm to integer in both systems', () => {
    // Shaft speeds are always whole revs/minute on every datasheet —
    // a fractional rpm reading is an extraction artifact.
    expect(convertValueUnit({ value: 3000.4, unit: 'rpm' }, 'metric')).toEqual({
      value: 3000,
      unit: 'rpm',
    });
    expect(convertValueUnit({ value: 1499.5, unit: 'rpm' }, 'metric')).toEqual({
      value: 1500,
      unit: 'rpm',
    });
    // rpm has no imperial conversion — must still round in imperial mode.
    expect(convertValueUnit({ value: 3000.7, unit: 'rpm' }, 'imperial')).toEqual({
      value: 3001,
      unit: 'rpm',
    });
  });

  it('passes through compound units (V/krpm, Nm/A)', () => {
    expect(convertValueUnit({ value: 7, unit: 'V/krpm' }, 'imperial')).toEqual({
      value: 7,
      unit: 'V/krpm',
    });
    expect(convertValueUnit({ value: 0.5, unit: 'Nm/A' }, 'imperial')).toEqual({
      value: 0.5,
      unit: 'Nm/A',
    });
  });

  it('relabels unit but passes value through for non-numeric strings', () => {
    const out = convertValueUnit({ value: '~5', unit: 'Nm' }, 'imperial');
    expect(out.value).toBe('~5');
    expect(out.unit).toBe('in·lb');
  });
});

describe('convertMinMaxUnit', () => {
  it('passes through unchanged in metric mode', () => {
    expect(
      convertMinMaxUnit({ min: 100, max: 240, unit: 'V' }, 'metric'),
    ).toEqual({ min: 100, max: 240, unit: 'V' });
  });

  it('converts °C range with offset', () => {
    const out = convertMinMaxUnit(
      { min: -20, max: 60, unit: '°C' },
      'imperial',
    );
    expect(out.unit).toBe('°F');
    expect(out.min).toBe(-4);
    expect(out.max).toBe(140);
  });

  it('preserves min ≤ max ordering', () => {
    const out = convertMinMaxUnit(
      { min: 0, max: 100, unit: 'mm' },
      'imperial',
    );
    expect(typeof out.min).toBe('number');
    expect(typeof out.max).toBe('number');
    expect(out.min as number).toBeLessThanOrEqual(out.max as number);
  });

  it('passes through unknown unit', () => {
    expect(
      convertMinMaxUnit({ min: 100, max: 240, unit: 'V' }, 'imperial'),
    ).toEqual({ min: 100, max: 240, unit: 'V' });
  });

  it('rounds voltage ranges to integers', () => {
    expect(
      convertMinMaxUnit({ min: 3.3, max: 5.5, unit: 'V' }, 'metric'),
    ).toEqual({ min: 3, max: 6, unit: 'V' });
  });

  it('rounds rpm ranges to integers', () => {
    expect(
      convertMinMaxUnit({ min: 0.4, max: 2999.7, unit: 'rpm' }, 'metric'),
    ).toEqual({ min: 0, max: 3000, unit: 'rpm' });
  });
});

describe('toCanonical', () => {
  it('returns input unchanged for metric mode', () => {
    expect(toCanonical(10, 'Nm', 'metric')).toBe(10);
  });

  it('inverts forward conversion for known unit', () => {
    // typed 10 in·lb in imperial mode → 1.13 Nm canonical
    const back = toCanonical(10, 'Nm', 'imperial');
    expect(back).toBeCloseTo(1.1298, 3);
  });

  it('returns input unchanged for unknown unit', () => {
    expect(toCanonical(24, 'V', 'imperial')).toBe(24);
  });

  it('inverts °F → °C', () => {
    expect(toCanonical(32, '°C', 'imperial')).toBeCloseTo(0, 5);
    expect(toCanonical(212, '°C', 'imperial')).toBeCloseTo(100, 5);
  });
});

describe('toDisplay', () => {
  it('returns input unchanged in metric mode', () => {
    expect(toDisplay(100, 'Nm', 'metric')).toBe(100);
  });

  it('converts forward in imperial mode', () => {
    expect(toDisplay(1, 'Nm', 'imperial')).toBeCloseTo(8.851, 2);
  });

  it('passes through unknown unit', () => {
    expect(toDisplay(24, 'V', 'imperial')).toBe(24);
  });

  it('rounds voltage to integer for histogram axes / slider readouts', () => {
    expect(toDisplay(3.3, 'V', 'metric')).toBe(3);
    expect(toDisplay(229.7, 'V', 'imperial')).toBe(230);
    expect(toDisplay(1.5, 'kV', 'metric')).toBe(2);
  });

  it('rounds rpm to integer for histogram axes / slider readouts', () => {
    expect(toDisplay(2999.4, 'rpm', 'metric')).toBe(2999);
    expect(toDisplay(2999.6, 'rpm', 'imperial')).toBe(3000);
  });
});

describe('displayUnit', () => {
  it('returns canonical unchanged in metric mode', () => {
    expect(displayUnit('Nm', 'metric')).toBe('Nm');
  });

  it('returns target unit in imperial mode', () => {
    expect(displayUnit('Nm', 'imperial')).toBe('in·lb');
    expect(displayUnit('mm', 'imperial')).toBe('in');
    expect(displayUnit('°C', 'imperial')).toBe('°F');
  });

  it('passes through units with no imperial form', () => {
    expect(displayUnit('V', 'imperial')).toBe('V');
    expect(displayUnit('rpm', 'imperial')).toBe('rpm');
    expect(displayUnit('V/krpm', 'imperial')).toBe('V/krpm');
  });
});
