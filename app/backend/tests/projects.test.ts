/**
 * Tests for /api/projects/* — user-owned project CRUD.
 *
 * Mocks the JWT verifier (so we don't need a live Cognito) and the
 * ProjectsService DynamoDB layer. Exercises the route wiring,
 * validation, ownership scoping, and response shape.
 */

import request from 'supertest';

const mockVerify = jest.fn();
jest.mock('aws-jwt-verify', () => ({
  CognitoJwtVerifier: { create: jest.fn(() => ({ verify: mockVerify })) },
}));

const mockList = jest.fn();
const mockGet = jest.fn();
const mockCreate = jest.fn();
const mockRename = jest.fn();
const mockDelete = jest.fn();
const mockAddProduct = jest.fn();
const mockRemoveProduct = jest.fn();
jest.mock('../src/db/projects', () => ({
  ProjectsService: jest.fn().mockImplementation(() => ({
    list: mockList,
    get: mockGet,
    create: mockCreate,
    rename: mockRename,
    delete: mockDelete,
    addProduct: mockAddProduct,
    removeProduct: mockRemoveProduct,
  })),
}));

// Stub the products DB so importing app doesn't try to talk to AWS.
jest.mock('../src/db/dynamodb');

import config from '../src/config';
import app from '../src/index';
import { _resetVerifierForTests } from '../src/middleware/auth';

const SUB = 'user-sub-1';
const OTHER_SUB = 'user-sub-2';
const TOKEN = 'Bearer test-token';

function authedUser(sub = SUB) {
  return { sub, email: `${sub}@example.com`, 'cognito:groups': [] };
}

beforeEach(() => {
  jest.clearAllMocks();
  _resetVerifierForTests();
  config.cognito.userPoolId = 'us-east-1_TEST';
  config.cognito.userPoolClientId = 'test-client-id';
  mockVerify.mockResolvedValue(authedUser());
});

describe('auth gating', () => {
  it('401s without a token', async () => {
    const res = await request(app).get('/api/projects');
    expect(res.status).toBe(401);
    expect(mockList).not.toHaveBeenCalled();
  });

  it('401s with an invalid token', async () => {
    mockVerify.mockRejectedValueOnce(new Error('bad'));
    const res = await request(app).get('/api/projects').set('Authorization', TOKEN);
    expect(res.status).toBe(401);
  });
});

describe('GET /api/projects', () => {
  it('lists only the caller’s projects', async () => {
    mockList.mockResolvedValueOnce([
      { id: 'p1', name: 'A', owner_sub: SUB, product_refs: [], created_at: 't', updated_at: 't' },
    ]);
    const res = await request(app).get('/api/projects').set('Authorization', TOKEN);
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.count).toBe(1);
    expect(mockList).toHaveBeenCalledWith(SUB);
  });

  it('strips PK/SK from responses', async () => {
    mockList.mockResolvedValueOnce([
      { id: 'p1', name: 'A', owner_sub: SUB, product_refs: [], created_at: 't', updated_at: 't', PK: `USER#${SUB}`, SK: 'PROJECT#p1' },
    ]);
    const res = await request(app).get('/api/projects').set('Authorization', TOKEN);
    expect(res.body.data[0].PK).toBeUndefined();
    expect(res.body.data[0].SK).toBeUndefined();
  });
});

describe('POST /api/projects', () => {
  it('400s on empty name', async () => {
    const res = await request(app)
      .post('/api/projects')
      .set('Authorization', TOKEN)
      .send({ name: '' });
    expect(res.status).toBe(400);
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it('400s on missing name', async () => {
    const res = await request(app).post('/api/projects').set('Authorization', TOKEN).send({});
    expect(res.status).toBe(400);
  });

  it('creates a project with owner_sub from token, ignores body owner_sub', async () => {
    mockCreate.mockResolvedValueOnce(undefined);
    const res = await request(app)
      .post('/api/projects')
      .set('Authorization', TOKEN)
      .send({ name: 'Cell A', owner_sub: OTHER_SUB });
    expect(res.status).toBe(201);
    expect(res.body.data.owner_sub).toBe(SUB);
    expect(res.body.data.name).toBe('Cell A');
    expect(res.body.data.product_refs).toEqual([]);
    expect(typeof res.body.data.id).toBe('string');
    const [callerSub, project] = mockCreate.mock.calls[0];
    expect(callerSub).toBe(SUB);
    expect(project.owner_sub).toBe(SUB);
  });

  it('trims whitespace in name', async () => {
    mockCreate.mockResolvedValueOnce(undefined);
    const res = await request(app)
      .post('/api/projects')
      .set('Authorization', TOKEN)
      .send({ name: '  Cell A  ' });
    expect(res.status).toBe(201);
    expect(res.body.data.name).toBe('Cell A');
  });
});

describe('GET /api/projects/:id', () => {
  it('200s with the project', async () => {
    mockGet.mockResolvedValueOnce({
      id: 'p1', name: 'A', owner_sub: SUB, product_refs: [], created_at: 't', updated_at: 't',
    });
    const res = await request(app).get('/api/projects/p1').set('Authorization', TOKEN);
    expect(res.status).toBe(200);
    expect(res.body.data.id).toBe('p1');
    expect(mockGet).toHaveBeenCalledWith(SUB, 'p1');
  });

  it('404s when not found', async () => {
    mockGet.mockResolvedValueOnce(null);
    const res = await request(app).get('/api/projects/nope').set('Authorization', TOKEN);
    expect(res.status).toBe(404);
  });

  it('scopes lookup to caller (cannot read other users’ project)', async () => {
    mockGet.mockResolvedValueOnce(null);
    const res = await request(app).get('/api/projects/p1').set('Authorization', TOKEN);
    expect(res.status).toBe(404);
    // Service is queried with caller's sub, never with a sub from the URL.
    expect(mockGet).toHaveBeenCalledWith(SUB, 'p1');
  });
});

describe('PATCH /api/projects/:id', () => {
  it('renames a project', async () => {
    mockRename.mockResolvedValueOnce({
      id: 'p1', name: 'New', owner_sub: SUB, product_refs: [], created_at: 't', updated_at: 't2',
    });
    const res = await request(app)
      .patch('/api/projects/p1')
      .set('Authorization', TOKEN)
      .send({ name: 'New' });
    expect(res.status).toBe(200);
    expect(res.body.data.name).toBe('New');
    expect(mockRename).toHaveBeenCalledWith(SUB, 'p1', 'New');
  });

  it('404s if project does not exist', async () => {
    mockRename.mockResolvedValueOnce(null);
    const res = await request(app)
      .patch('/api/projects/missing')
      .set('Authorization', TOKEN)
      .send({ name: 'New' });
    expect(res.status).toBe(404);
  });

  it('400s on empty name', async () => {
    const res = await request(app)
      .patch('/api/projects/p1')
      .set('Authorization', TOKEN)
      .send({ name: '   ' });
    expect(res.status).toBe(400);
    expect(mockRename).not.toHaveBeenCalled();
  });
});

describe('DELETE /api/projects/:id', () => {
  it('deletes', async () => {
    mockDelete.mockResolvedValueOnce(true);
    const res = await request(app).delete('/api/projects/p1').set('Authorization', TOKEN);
    expect(res.status).toBe(200);
    expect(res.body.data.deleted).toBe(true);
    expect(mockDelete).toHaveBeenCalledWith(SUB, 'p1');
  });

  it('404s if not found', async () => {
    mockDelete.mockResolvedValueOnce(false);
    const res = await request(app).delete('/api/projects/missing').set('Authorization', TOKEN);
    expect(res.status).toBe(404);
  });
});

describe('POST /api/projects/:id/products', () => {
  it('adds a product ref', async () => {
    mockAddProduct.mockResolvedValueOnce({
      id: 'p1', name: 'A', owner_sub: SUB,
      product_refs: [{ product_type: 'motor', product_id: 'm-1' }],
      created_at: 't', updated_at: 't2',
    });
    const res = await request(app)
      .post('/api/projects/p1/products')
      .set('Authorization', TOKEN)
      .send({ product_type: 'motor', product_id: 'm-1' });
    expect(res.status).toBe(200);
    expect(res.body.data.product_refs).toHaveLength(1);
    expect(mockAddProduct).toHaveBeenCalledWith(SUB, 'p1', { product_type: 'motor', product_id: 'm-1' });
  });

  it('400s on missing product_id', async () => {
    const res = await request(app)
      .post('/api/projects/p1/products')
      .set('Authorization', TOKEN)
      .send({ product_type: 'motor' });
    expect(res.status).toBe(400);
  });

  it('404s if project not found', async () => {
    mockAddProduct.mockResolvedValueOnce(null);
    const res = await request(app)
      .post('/api/projects/nope/products')
      .set('Authorization', TOKEN)
      .send({ product_type: 'motor', product_id: 'm-1' });
    expect(res.status).toBe(404);
  });
});

describe('DELETE /api/projects/:id/products/:type/:pid', () => {
  it('removes a product ref', async () => {
    mockRemoveProduct.mockResolvedValueOnce({
      id: 'p1', name: 'A', owner_sub: SUB, product_refs: [],
      created_at: 't', updated_at: 't2',
    });
    const res = await request(app)
      .delete('/api/projects/p1/products/motor/m-1')
      .set('Authorization', TOKEN);
    expect(res.status).toBe(200);
    expect(res.body.data.product_refs).toEqual([]);
    expect(mockRemoveProduct).toHaveBeenCalledWith(SUB, 'p1', { product_type: 'motor', product_id: 'm-1' });
  });

  it('404s if project not found', async () => {
    mockRemoveProduct.mockResolvedValueOnce(null);
    const res = await request(app)
      .delete('/api/projects/nope/products/motor/m-1')
      .set('Authorization', TOKEN);
    expect(res.status).toBe(404);
  });
});

describe('readonly guard', () => {
  it('does not block POST /api/projects in public mode', async () => {
    // The guard runs on all /api routes when APP_MODE=public — projects
    // are exempt because the route enforces ownership via requireAuth.
    mockCreate.mockResolvedValueOnce(undefined);
    const res = await request(app)
      .post('/api/projects')
      .set('Authorization', TOKEN)
      .send({ name: 'A' });
    expect(res.status).not.toBe(403);
    expect(res.status).toBe(201);
  });
});
