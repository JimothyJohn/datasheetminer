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

  it('converts °C → °F (offset, not multiplier)', () => {
    expect(convertValueUnit({ value: 0, unit: '°C' }, 'imperial').value).toBe(32);
    const minus40 = convertValueUnit({ value: -40, unit: '°C' }, 'imperial');
    expect(minus40.value).toBeCloseTo(-40, 5);
    expect(minus40.unit).toBe('°F');
    const hundred = convertValueUnit({ value: 100, unit: '°C' }, 'imperial');
    expect(hundred.value).toBe(212);
  });

  it('passes through unknown units (V, A, rpm)', () => {
    expect(convertValueUnit({ value: 24, unit: 'V' }, 'imperial')).toEqual({
      value: 24,
      unit: 'V',
    });
    expect(convertValueUnit({ value: 3000, unit: 'rpm' }, 'imperial')).toEqual({
      value: 3000,
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
