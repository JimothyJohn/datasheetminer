/**
 * Tests for the rotary-chain compat service and its HTTP route.
 * Mirrors the Python tests in tests/unit/test_integration.py for the
 * drive↔motor and motor↔gearhead junctions, in fits-partial mode.
 */

import request from 'supertest';
import app from '../src/index';
import { DynamoDBService } from '../src/db/dynamodb';
import { check, isPairSupported, softenReport, ADJACENT_TYPES } from '../src/services/compat';
import { Drive, Gearhead, Motor } from '../src/types/models';

jest.mock('../src/db/dynamodb');

function makeMotor(over: Partial<Motor> = {}): Motor {
  return {
    PK: 'PRODUCT#MOTOR',
    SK: 'PRODUCT#m1',
    product_id: 'm1',
    product_type: 'motor',
    manufacturer: 'TestCo',
    rated_voltage: { min: 200, max: 240, unit: 'V' },
    rated_current: { value: 5, unit: 'A' },
    rated_power: { value: 1000, unit: 'W' },
    rated_speed: { value: 3000, unit: 'rpm' },
    rated_torque: { value: 3, unit: 'Nm' },
    shaft_diameter: { value: 14, unit: 'mm' },
    frame_size: '60',
    encoder_feedback_support: 'EnDat 2.2',
    type: 'ac servo',
    ...over,
  };
}

function makeDrive(over: Partial<Drive> = {}): Drive {
  return {
    PK: 'PRODUCT#DRIVE',
    SK: 'PRODUCT#d1',
    product_id: 'd1',
    product_type: 'drive',
    manufacturer: 'TestCo',
    input_voltage: { min: 200, max: 240, unit: 'V' },
    rated_current: { value: 10, unit: 'A' },
    rated_power: { value: 2000, unit: 'W' },
    encoder_feedback_support: ['EnDat 2.2', 'Resolver'],
    fieldbus: ['EtherCAT'],
    ...over,
  };
}

function makeGearhead(over: Partial<Gearhead> = {}): Gearhead {
  return {
    PK: 'PRODUCT#GEARHEAD',
    SK: 'PRODUCT#g1',
    product_id: 'g1',
    product_type: 'gearhead',
    manufacturer: 'TestCo',
    gear_ratio: 10,
    frame_size: '60',
    input_shaft_diameter: { value: 14, unit: 'mm' },
    max_input_speed: { value: 4000, unit: 'rpm' },
    rated_torque: { value: 30, unit: 'Nm' },
    ...over,
  };
}

describe('compat service — supported pairs', () => {
  it('drive↔motor and motor↔gearhead are supported (both orderings)', () => {
    expect(isPairSupported('drive', 'motor')).toBe(true);
    expect(isPairSupported('motor', 'drive')).toBe(true);
    expect(isPairSupported('motor', 'gearhead')).toBe(true);
    expect(isPairSupported('gearhead', 'motor')).toBe(true);
  });

  it('drive↔gearhead is not supported (no direct junction)', () => {
    expect(isPairSupported('drive', 'gearhead')).toBe(false);
    expect(isPairSupported('gearhead', 'drive')).toBe(false);
  });

  it('exposes the rotary-chain adjacency map for the UI picker', () => {
    expect(ADJACENT_TYPES.drive).toEqual(['motor']);
    expect(ADJACENT_TYPES.motor).toEqual(['drive', 'gearhead']);
    expect(ADJACENT_TYPES.gearhead).toEqual(['motor']);
  });
});

describe('compat service — drive↔motor', () => {
  it('reports ok when current/voltage/power line up and encoder is supported', () => {
    const r = check(makeDrive(), makeMotor());
    expect(r.status).toBe('ok');
    const power = r.results.find(p => p.from_port === 'Drive.motor_output');
    expect(power?.status).toBe('ok');
  });

  it('reports strict fail for an undersized drive current', () => {
    const r = check(makeDrive({ rated_current: { value: 2, unit: 'A' } }), makeMotor());
    expect(r.status).toBe('fail');
    const power = r.results.find(p => p.from_port === 'Drive.motor_output')!;
    const current = power.checks.find(c => c.field === 'current')!;
    expect(current.status).toBe('fail');
    expect(current.detail).toContain('supply 2 < demand 5');
  });

  it('softens that same fail to partial at the API boundary', () => {
    const strict = check(makeDrive({ rated_current: { value: 2, unit: 'A' } }), makeMotor());
    const soft = softenReport(strict);
    expect(soft.status).toBe('partial');
    const power = soft.results.find(p => p.from_port === 'Drive.motor_output')!;
    const current = power.checks.find(c => c.field === 'current')!;
    expect(current.status).toBe('partial');
    // Detail is preserved so the UI can still show what didn't line up.
    expect(current.detail).toContain('supply 2 < demand 5');
  });

  it('reports strict fail for an unsupported encoder', () => {
    const r = check(
      makeDrive({ encoder_feedback_support: ['Resolver'] }),
      makeMotor({ encoder_feedback_support: 'EnDat 2.2' }),
    );
    const fb = r.results.find(p => p.from_port === 'Drive.feedback')!;
    expect(fb.status).toBe('fail');
  });

  it('treats missing fields as partial, not ok and not fail', () => {
    const r = check(makeDrive({ rated_power: undefined }), makeMotor({ rated_power: undefined }));
    const power = r.results.find(p => p.from_port === 'Drive.motor_output')!;
    const p = power.checks.find(c => c.field === 'power')!;
    expect(p.status).toBe('partial');
  });

  it('works when motor is passed first (compat is order-agnostic)', () => {
    const r = check(makeMotor(), makeDrive());
    expect(r.from_type).toBe('drive');
    expect(r.to_type).toBe('motor');
  });
});

describe('compat service — motor↔gearhead', () => {
  it('reports ok when frame size, shaft, and speed all agree', () => {
    const r = check(makeMotor(), makeGearhead());
    expect(r.status).toBe('ok');
  });

  it('shaft mismatch is strict fail and softens to partial', () => {
    const strict = check(
      makeMotor({ shaft_diameter: { value: 10, unit: 'mm' } }),
      makeGearhead({ input_shaft_diameter: { value: 14, unit: 'mm' } }),
    );
    expect(strict.status).toBe('fail');
    expect(softenReport(strict).status).toBe('partial');
  });

  it('motor overspeed is strict fail and softens', () => {
    const strict = check(
      makeMotor({ rated_speed: { value: 5000, unit: 'rpm' } }),
      makeGearhead({ max_input_speed: { value: 4000, unit: 'rpm' } }),
    );
    const shaft = strict.results.find(p => p.from_port === 'Motor.shaft_output')!;
    const speed = shaft.checks.find(c => c.field === 'speed')!;
    expect(speed.status).toBe('fail');
    expect(softenReport(strict).status).toBe('partial');
  });
});

describe('POST /api/v1/compat/check', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns a CompatibilityReport for a valid drive↔motor pair', async () => {
    (DynamoDBService.prototype.read as jest.Mock).mockImplementation(
      async (_id: string, type: string) => (type === 'drive' ? makeDrive() : makeMotor()),
    );
    const res = await request(app)
      .post('/api/v1/compat/check')
      .send({ a: { id: 'd1', type: 'drive' }, b: { id: 'm1', type: 'motor' } });
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.data.from_type).toBe('drive');
    expect(res.body.data.to_type).toBe('motor');
    expect(['ok', 'partial']).toContain(res.body.data.status);
  });

  it('400s on unsupported pair (drive↔gearhead has no direct junction)', async () => {
    const res = await request(app)
      .post('/api/v1/compat/check')
      .send({ a: { id: 'd1', type: 'drive' }, b: { id: 'g1', type: 'gearhead' } });
    expect(res.status).toBe(400);
  });

  it('400s on invalid body shape', async () => {
    const res = await request(app)
      .post('/api/v1/compat/check')
      .send({ a: { id: 'd1' }, b: { id: 'm1', type: 'motor' } });
    expect(res.status).toBe(400);
  });

  it('404s when one product is missing', async () => {
    (DynamoDBService.prototype.read as jest.Mock).mockImplementation(
      async (_id: string, type: string) => (type === 'drive' ? makeDrive() : null),
    );
    const res = await request(app)
      .post('/api/v1/compat/check')
      .send({ a: { id: 'd1', type: 'drive' }, b: { id: 'missing', type: 'motor' } });
    expect(res.status).toBe(404);
  });
});

describe('GET /api/v1/compat/adjacent', () => {
  it('returns the adjacent types for a given product type', async () => {
    const res = await request(app).get('/api/v1/compat/adjacent?type=motor');
    expect(res.status).toBe(200);
    expect(res.body.data).toEqual(['drive', 'gearhead']);
  });

  it('returns an empty list for unknown types', async () => {
    const res = await request(app).get('/api/v1/compat/adjacent?type=unknown');
    expect(res.status).toBe(200);
    expect(res.body.data).toEqual([]);
  });
});
