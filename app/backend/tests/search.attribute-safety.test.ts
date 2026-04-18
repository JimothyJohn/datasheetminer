/**
 * Attribute-safety tests for GET /api/v1/search.
 *
 * The route accepts `where` and `sort` parameters that name a Product field.
 * `getProductField` does a bare `(product as ...)[field]` lookup, which
 * traverses the prototype chain. Reserved property names like `__proto__`,
 * `constructor`, `toString`, etc. should NEVER cause:
 *   - a 500 (crash)
 *   - reflected attacker content back to the client
 *   - prototype pollution of the live product objects
 *
 * If the route ever grows a strict attribute allowlist, these tests verify
 * the rejection story without changing.
 */

import request from 'supertest';
import app from '../src/index';
import { DynamoDBService } from '../src/db/dynamodb';
import { Product } from '../src/types/models';

jest.mock('../src/db/dynamodb');

const mockProducts = [
  {
    product_id: 'a',
    product_type: 'motor',
    manufacturer: 'Acme',
    product_name: 'X',
    rated_power: { value: 100, unit: 'W' },
  },
  {
    product_id: 'b',
    product_type: 'motor',
    manufacturer: 'Beta',
    product_name: 'Y',
    rated_power: { value: 50, unit: 'W' },
  },
] as unknown as Product[];

beforeEach(() => {
  jest.clearAllMocks();
  (DynamoDBService.prototype.list as jest.Mock).mockResolvedValue(mockProducts);
});

describe('where= reserved property names', () => {
  it.each([
    '__proto__>0',
    'constructor>0',
    'prototype>0',
    'toString>0',
    'hasOwnProperty>0',
    'valueOf>0',
  ])('where=%s does not 500 and does not match products', async (expr) => {
    const res = await request(app)
      .get('/api/v1/search')
      .query({ where: expr });
    expect(res.status).toBeLessThan(500);
    if (res.status === 200) {
      // Reserved-word fields should not match any real product — count == 0.
      expect(res.body.count).toBe(0);
    }
  });

  it('where=__proto__.polluted=1 does not mutate Object.prototype', async () => {
    await request(app)
      .get('/api/v1/search')
      .query({ where: '__proto__.polluted=1' });
    expect(({} as Record<string, unknown>).polluted).toBeUndefined();
  });
});

describe('sort= reserved property names', () => {
  it.each(['__proto__', 'constructor', 'prototype:desc', 'toString:asc'])(
    'sort=%s does not 500',
    async (expr) => {
      const res = await request(app)
        .get('/api/v1/search')
        .query({ sort: expr });
      expect(res.status).toBeLessThan(500);
    },
  );
});

describe('dotted path attributes', () => {
  it.each([
    'rated_power.value>50',
    'rated_power.unit=W',
    'rated_voltage.min>=10',
  ])('where=%s is either ignored or handled — never 500', async (expr) => {
    const res = await request(app)
      .get('/api/v1/search')
      .query({ where: expr });
    expect(res.status).toBeLessThan(500);
  });
});

describe('response does not echo attacker-controlled field name', () => {
  it('unknown field name is not reflected unescaped in error body', async () => {
    const xss = '<img src=x onerror=1>';
    const res = await request(app)
      .get('/api/v1/search')
      .query({ where: `${xss}>0` });
    expect(res.status).toBeLessThan(500);
    const body = JSON.stringify(res.body);
    // Field name may appear in error text, but only as JSON-escaped content.
    // Critical check: no raw HTML tags in response body.
    expect(body).not.toMatch(/<img[^>]*onerror/);
  });
});
