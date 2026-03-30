/**
 * Tests for compact unit string parsing in DynamoDB deserialization.
 * Python stores specs as "value;unit" and "min-max;unit" strings.
 * The Node.js backend must parse these into {value, unit} / {min, max, unit} objects.
 */

import { DynamoDBService } from '../src/db/dynamodb';

// Don't mock DynamoDB — we need the real parseCompactUnits method
jest.mock('@aws-sdk/client-dynamodb');
jest.mock('@aws-sdk/util-dynamodb', () => ({
  marshall: jest.fn((obj) => obj),
  unmarshall: jest.fn((obj) => obj),
}));

describe('parseCompactUnits', () => {
  let db: DynamoDBService;

  beforeEach(() => {
    db = new DynamoDBService({ tableName: 'test-table' });
  });

  // =================== ValueUnit strings ===================

  it('parses "100;W" into {value: 100, unit: "W"}', () => {
    const result = (db as any).parseCompactUnits('100;W');
    expect(result).toEqual({ value: 100, unit: 'W' });
  });

  it('parses "3000;rpm" into {value: 3000, unit: "rpm"}', () => {
    const result = (db as any).parseCompactUnits('3000;rpm');
    expect(result).toEqual({ value: 3000, unit: 'rpm' });
  });

  it('parses "0.5;Nm" into {value: 0.5, unit: "Nm"}', () => {
    const result = (db as any).parseCompactUnits('0.5;Nm');
    expect(result).toEqual({ value: 0.5, unit: 'Nm' });
  });

  it('parses comma-separated thousands "1,500;W"', () => {
    const result = (db as any).parseCompactUnits('1,500;W');
    expect(result).toEqual({ value: 1500, unit: 'W' });
  });

  it('parses "3,000;min-1"', () => {
    const result = (db as any).parseCompactUnits('3,000;min-1');
    expect(result).toEqual({ value: 3000, unit: 'min-1' });
  });

  // =================== MinMaxUnit strings ===================

  it('parses "20-40;C" into {min: 20, max: 40, unit: "C"}', () => {
    const result = (db as any).parseCompactUnits('20-40;C');
    expect(result).toEqual({ min: 20, max: 40, unit: 'C' });
  });

  it('parses "24-48;V" into {min: 24, max: 48, unit: "V"}', () => {
    const result = (db as any).parseCompactUnits('24-48;V');
    expect(result).toEqual({ min: 24, max: 48, unit: 'V' });
  });

  it('parses negative range "-20-40;C"', () => {
    const result = (db as any).parseCompactUnits('-20-40;C');
    expect(result).toEqual({ min: -20, max: 40, unit: 'C' });
  });

  it('parses "220-530;W" range', () => {
    const result = (db as any).parseCompactUnits('220-530;W');
    expect(result).toEqual({ min: 220, max: 530, unit: 'W' });
  });

  // =================== Non-matching strings pass through ===================

  it('passes through strings without semicolons', () => {
    expect((db as any).parseCompactUnits('brushless dc')).toBe('brushless dc');
  });

  it('passes through non-numeric semicolon strings', () => {
    expect((db as any).parseCompactUnits('abc;def')).toBe('abc;def');
  });

  it('passes through numbers', () => {
    expect((db as any).parseCompactUnits(42)).toBe(42);
  });

  it('passes through null', () => {
    expect((db as any).parseCompactUnits(null)).toBeNull();
  });

  it('passes through undefined', () => {
    expect((db as any).parseCompactUnits(undefined)).toBeUndefined();
  });

  // =================== Recursive parsing ===================

  it('recursively parses objects', () => {
    const input = {
      product_type: 'motor',
      rated_power: '1,500;W',
      rated_speed: '3,000;min-1',
      rated_voltage: '24-48;V',
      manufacturer: 'Omron',
    };

    const result = (db as any).parseCompactUnits(input);
    expect(result.rated_power).toEqual({ value: 1500, unit: 'W' });
    expect(result.rated_speed).toEqual({ value: 3000, unit: 'min-1' });
    expect(result.rated_voltage).toEqual({ min: 24, max: 48, unit: 'V' });
    expect(result.manufacturer).toBe('Omron');
    expect(result.product_type).toBe('motor');
  });

  it('recursively parses arrays', () => {
    const input = ['100;W', '200;W'];
    const result = (db as any).parseCompactUnits(input);
    expect(result).toEqual([
      { value: 100, unit: 'W' },
      { value: 200, unit: 'W' },
    ]);
  });

  it('handles nested objects', () => {
    const input = {
      specs: {
        power: '500;W',
        temp: '-10-50;C',
      },
    };
    const result = (db as any).parseCompactUnits(input);
    expect(result.specs.power).toEqual({ value: 500, unit: 'W' });
    expect(result.specs.temp).toEqual({ min: -10, max: 50, unit: 'C' });
  });

  // =================== Already-parsed objects pass through ===================

  it('passes through already-parsed ValueUnit objects', () => {
    const input = { value: 100, unit: 'W' };
    const result = (db as any).parseCompactUnits(input);
    expect(result).toEqual({ value: 100, unit: 'W' });
  });

  it('passes through already-parsed MinMaxUnit objects', () => {
    const input = { min: 24, max: 48, unit: 'V' };
    const result = (db as any).parseCompactUnits(input);
    expect(result).toEqual({ min: 24, max: 48, unit: 'V' });
  });
});

describe('deserializeProduct with compact units', () => {
  let db: DynamoDBService;

  beforeEach(() => {
    db = new DynamoDBService({ tableName: 'test-table' });
  });

  it('parses compact strings in a motor product', () => {
    const raw = {
      product_id: '123',
      product_type: 'motor',
      manufacturer: 'Omron',
      product_name: 'G-Series',
      rated_power: '1,500;W',
      rated_speed: '3,000;min-1',
      rated_voltage: '200-230;V',
    };

    const result = (db as any).deserializeProduct(raw);
    expect(result.rated_power).toEqual({ value: 1500, unit: 'W' });
    expect(result.rated_speed).toEqual({ value: 3000, unit: 'min-1' });
    expect(result.rated_voltage).toEqual({ min: 200, max: 230, unit: 'V' });
    expect(result.manufacturer).toBe('Omron');
  });

  it('handles mixed parsed and unparsed fields', () => {
    const raw = {
      product_id: '456',
      product_type: 'motor',
      manufacturer: 'Test',
      rated_power: { value: 100, unit: 'W' }, // already parsed
      rated_speed: '3000;rpm', // compact string
    };

    const result = (db as any).deserializeProduct(raw);
    expect(result.rated_power).toEqual({ value: 100, unit: 'W' });
    expect(result.rated_speed).toEqual({ value: 3000, unit: 'rpm' });
  });

  it('parses compact strings in datasheet products', () => {
    const raw = {
      datasheet_id: 'ds-1',
      product_type: 'datasheet',
      url: 'https://example.com/test.pdf',
      rated_power: '500;W',
    };

    const result = (db as any).deserializeProduct(raw);
    expect(result.product_id).toBe('ds-1');
    expect(result.rated_power).toEqual({ value: 500, unit: 'W' });
  });
});
