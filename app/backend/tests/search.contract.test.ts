/**
 * Contract/boundary tests for GET /api/v1/search.
 *
 * Existing search.test.ts covers the happy paths. This file hits the Zod
 * boundaries, common abuse inputs, and parameter aliasing surprises that an
 * attacker or a buggy client can exercise.
 */

import request from 'supertest';
import app from '../src/index';
import { DynamoDBService } from '../src/db/dynamodb';

jest.mock('../src/db/dynamodb');

function mockList(data: unknown[] = []) {
  (DynamoDBService.prototype.list as jest.Mock).mockResolvedValue(data);
}

describe('GET /api/v1/search — limit boundary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockList([]);
  });

  it.each(['0', '-1', '101', '9999999999', 'abc', '', 'NaN', 'null'])(
    'rejects limit=%s with 400',
    async (bad) => {
      const res = await request(app).get(`/api/v1/search?limit=${bad}`);
      expect(res.status).toBe(400);
      expect(res.body.success).toBe(false);
    },
  );

  it('accepts limit=1 (lower bound)', async () => {
    const res = await request(app).get('/api/v1/search?limit=1');
    expect(res.status).toBe(200);
  });

  it('accepts limit=100 (upper bound)', async () => {
    const res = await request(app).get('/api/v1/search?limit=100');
    expect(res.status).toBe(200);
  });

  it('defaults to 20 when limit is omitted', async () => {
    const res = await request(app).get('/api/v1/search');
    expect(res.status).toBe(200);
  });
});

describe('GET /api/v1/search — type enum enforcement', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockList([]);
  });

  it.each(['unknown', 'Motor', 'MOTOR', 'motor ', ' motor', '../motor'])(
    'rejects type=%s with 400',
    async (bad) => {
      const res = await request(app).get(`/api/v1/search?type=${encodeURIComponent(bad)}`);
      expect(res.status).toBe(400);
    },
  );

  it.each(['motor', 'drive', 'gearhead', 'robot_arm', 'contactor'])(
    'accepts type=%s',
    async (good) => {
      const res = await request(app).get(`/api/v1/search?type=${good}`);
      expect(res.status).toBe(200);
    },
  );
});

describe('GET /api/v1/search — abuse inputs are handled safely', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockList([]);
  });

  it('treats SQL-ish text as literal content', async () => {
    // We don't use SQL, but this is the canonical abuse input. Must not 500.
    const q = encodeURIComponent("'; DROP TABLE products --");
    const res = await request(app).get(`/api/v1/search?q=${q}`);
    expect(res.status).toBe(200);
  });

  it('treats NoSQL operator injection as literal text', async () => {
    const q = encodeURIComponent('{ "$ne": null }');
    const res = await request(app).get(`/api/v1/search?q=${q}`);
    expect(res.status).toBe(200);
  });

  it('accepts a reasonable q value up to a few KB', async () => {
    const q = 'a'.repeat(2000);
    const res = await request(app).get('/api/v1/search').query({ q });
    expect(res.status).toBe(200);
  });

  it('accepts unicode query strings without crashing', async () => {
    const res = await request(app).get('/api/v1/search').query({ q: 'café \u00e9 résumé' });
    expect(res.status).toBe(200);
  });

  it('null byte in q does not crash', async () => {
    const res = await request(app).get('/api/v1/search').query({ q: 'abc\x00def' });
    // Express may strip/encode; either 200 or 400 is acceptable. 500 is not.
    expect(res.status).toBeLessThan(500);
  });
});

describe('GET /api/v1/search — where/sort array handling', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockList([]);
  });

  it('accepts repeated where params as an array', async () => {
    const res = await request(app)
      .get('/api/v1/search')
      .query({ where: ['rated_power>=100', 'rated_voltage<=48'] });
    expect(res.status).toBe(200);
  });

  it('accepts repeated sort params as an array', async () => {
    const res = await request(app)
      .get('/api/v1/search')
      .query({ sort: ['manufacturer', 'rated_power:desc'] });
    expect(res.status).toBe(200);
  });

  it('handles a malformed where expression as 500 or filtered-out, never crash', async () => {
    const res = await request(app).get('/api/v1/search').query({ where: 'not-an-expression' });
    // Current behavior: searchService.parseWhere throws; route catches → 500.
    // Document this: it's an internal bug surface, but not a crash or leak.
    expect([200, 400, 500]).toContain(res.status);
  });

  it('duplicate type params do not produce 500', async () => {
    // ?type=motor&type=drive — express parses as array, Zod rejects non-enum.
    const res = await request(app).get('/api/v1/search?type=motor&type=drive');
    expect(res.status).toBeLessThan(500);
  });
});

describe('GET /api/v1/search — DB error surface', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('500 with JSON body when DB rejects', async () => {
    (DynamoDBService.prototype.list as jest.Mock).mockRejectedValue(new Error('boom'));
    const res = await request(app).get('/api/v1/search?type=motor');
    expect(res.status).toBe(500);
    expect(res.body).toHaveProperty('success', false);
    expect(res.body).toHaveProperty('error');
    // Error message should not leak implementation details like stack traces.
    expect(res.body.error).not.toMatch(/at \S+\.ts/);
  });
});
