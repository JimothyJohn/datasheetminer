/**
 * Tests for formatting utility functions
 */

import { describe, it, expect } from 'vitest';
import { formatPropertyLabel, formatValue } from './formatting';

describe('formatPropertyLabel', () => {
  it('capitalizes regular words', () => {
    expect(formatPropertyLabel('rated_voltage')).toBe('Rated Voltage');
  });

  it('uppercases known acronyms', () => {
    expect(formatPropertyLabel('ip_rating')).toBe('IP Rating');
    expect(formatPropertyLabel('ac_input')).toBe('AC Input');
    expect(formatPropertyLabel('dc_output')).toBe('DC Output');
    expect(formatPropertyLabel('pwm_frequency')).toBe('PWM Frequency');
  });

  it('handles single word', () => {
    expect(formatPropertyLabel('weight')).toBe('Weight');
  });

  it('handles single acronym', () => {
    expect(formatPropertyLabel('url')).toBe('URL');
  });

  it('handles multiple acronyms', () => {
    expect(formatPropertyLabel('io_api')).toBe('IO API');
  });

  it('handles mixed acronyms and words', () => {
    expect(formatPropertyLabel('max_rpm')).toBe('Max RPM');
    expect(formatPropertyLabel('usb_port_count')).toBe('USB Port Count');
  });

  it('handles empty string', () => {
    expect(formatPropertyLabel('')).toBe('');
  });
});

describe('formatValue', () => {
  it('returns empty string for null', () => {
    expect(formatValue(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(formatValue(undefined)).toBe('');
  });

  it('converts string to string', () => {
    expect(formatValue('hello')).toBe('hello');
  });

  it('converts number to string', () => {
    expect(formatValue(42)).toBe('42');
  });

  it('converts boolean to string', () => {
    expect(formatValue(true)).toBe('true');
  });

  it('formats value+unit object', () => {
    expect(formatValue({ value: 3000, unit: 'rpm' })).toBe('3000 rpm');
  });

  it('formats min+max+unit object', () => {
    expect(formatValue({ min: 100, max: 240, unit: 'V' })).toBe('100-240 V');
  });

  it('formats nominal+unit object', () => {
    expect(formatValue({ nominal: 24, unit: 'V' })).toBe('24 V');
  });

  it('formats rated+unit object', () => {
    expect(formatValue({ rated: 5, unit: 'A' })).toBe('5 A');
  });

  it('formats min+max without unit', () => {
    expect(formatValue({ min: 0, max: 100 })).toBe('0-100');
  });

  it('returns empty string for empty array', () => {
    expect(formatValue([])).toBe('');
  });

  it('formats string array', () => {
    expect(formatValue(['EtherCAT', 'CANopen'])).toBe('EtherCAT, CANopen');
  });

  it('formats array of value+unit objects', () => {
    const arr = [
      { value: 4000, unit: 'Hz' },
      { value: 8000, unit: 'Hz' },
    ];
    expect(formatValue(arr)).toBe('4000, 8000 Hz');
  });

  it('formats array of min+max+unit objects', () => {
    const arr = [
      { min: 50, max: 60, unit: 'Hz' },
      { min: 47, max: 63, unit: 'Hz' },
    ];
    expect(formatValue(arr)).toBe('50-60, 47-63 Hz');
  });

  it('formats nested object as key-value pairs', () => {
    const result = formatValue({ width: 100, height: 50, unit: 'mm' });
    expect(result).toContain('Width: 100');
    expect(result).toContain('Height: 50');
    expect(result).toContain('mm');
  });

  it('filters out missing entries from nested objects', () => {
    const result = formatValue({ width: 100, height: null, unit: 'mm' });
    expect(result).not.toContain('Height');
  });

  it('respects max depth', () => {
    expect(formatValue({ a: 1 }, 6, 5)).toBe('[Max depth exceeded]');
  });

  it('returns empty string for object with all missing values', () => {
    expect(formatValue({ a: null, b: undefined })).toBe('');
  });

  it('default (no system arg) keeps metric output stable', () => {
    expect(formatValue({ value: 100, unit: 'N' })).toBe('100 N');
  });

  it('imperial flips ValueUnit (Nm → in·lb)', () => {
    const out = formatValue({ value: 1, unit: 'Nm' }, 0, 5, 'imperial');
    expect(out).toContain('in·lb');
    expect(out).toMatch(/^8\.85/);
  });

  it('imperial flips MinMaxUnit temperature with offset', () => {
    expect(
      formatValue({ min: -20, max: 60, unit: '°C' }, 0, 5, 'imperial'),
    ).toBe('-4-140 °F');
  });

  it('imperial leaves voltage (no idiomatic imperial) unchanged', () => {
    expect(formatValue({ value: 24, unit: 'V' }, 0, 5, 'imperial')).toBe('24 V');
  });

  it('imperial flips dimensions object with shared unit', () => {
    const out = formatValue(
      { width: 100, height: 50, unit: 'mm' },
      0,
      5,
      'imperial',
    );
    expect(out).toContain('in');
    expect(out).not.toContain(' mm');
  });
});
