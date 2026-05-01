/**
 * Tests for the requireAuth / optionalAuth / requireGroup middleware.
 *
 * The Cognito JWT verifier is mocked at the aws-jwt-verify module
 * boundary so these tests don't need network access or live Cognito.
 */

import { Request, Response, NextFunction } from 'express';
import config from '../src/config';

const mockVerify = jest.fn();

jest.mock('aws-jwt-verify', () => ({
  CognitoJwtVerifier: { create: jest.fn(() => ({ verify: mockVerify })) },
}));

// Import after the mock so the cached verifier (if any) builds against
// the mocked factory.
import { requireAuth, optionalAuth, requireGroup, _resetVerifierForTests } from '../src/middleware/auth';

function mockRes(): any {
  const res: any = {
    _status: 0,
    _body: null,
    status(code: number) { res._status = code; return res; },
    json(body: any) { res._body = body; return res; },
  };
  return res;
}

describe('requireAuth', () => {
  const origPoolId = config.cognito.userPoolId;
  const origClientId = config.cognito.userPoolClientId;

  beforeEach(() => {
    _resetVerifierForTests();
    mockVerify.mockReset();
    config.cognito.userPoolId = 'us-east-1_TEST';
    config.cognito.userPoolClientId = 'test-client-id';
  });

  afterAll(() => {
    config.cognito.userPoolId = origPoolId;
    config.cognito.userPoolClientId = origClientId;
  });

  it('returns 503 if Cognito is not configured', async () => {
    config.cognito.userPoolId = '';
    config.cognito.userPoolClientId = '';
    _resetVerifierForTests();

    const req = { headers: { authorization: 'Bearer x' } } as Request;
    const res = mockRes();
    let nextCalled = false;
    await requireAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(res._status).toBe(503);
    expect(nextCalled).toBe(false);
  });

  it('returns 401 when no Authorization header is set', async () => {
    const req = { headers: {} } as Request;
    const res = mockRes();
    let nextCalled = false;
    await requireAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(res._status).toBe(401);
    expect(res._body.error).toMatch(/bearer/i);
    expect(nextCalled).toBe(false);
  });

  it('returns 401 when the token is malformed (no Bearer prefix)', async () => {
    const req = { headers: { authorization: 'sometoken' } } as Request;
    const res = mockRes();
    await requireAuth(req, res as Response, (() => undefined) as NextFunction);
    expect(res._status).toBe(401);
  });

  it('returns 401 when token verification throws', async () => {
    mockVerify.mockRejectedValueOnce(new Error('expired'));
    const req = { headers: { authorization: 'Bearer bad-token' } } as Request;
    const res = mockRes();
    let nextCalled = false;
    await requireAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(res._status).toBe(401);
    expect(res._body.error).toMatch(/invalid|expired/i);
    expect(nextCalled).toBe(false);
  });

  it('attaches req.user and calls next on a valid token', async () => {
    mockVerify.mockResolvedValueOnce({
      sub: 'user-123',
      email: 'a@example.com',
      'cognito:groups': ['admin'],
    });
    const req = { headers: { authorization: 'Bearer good-token' } } as Request;
    const res = mockRes();
    let nextCalled = false;
    await requireAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(nextCalled).toBe(true);
    expect(req.user).toEqual({
      sub: 'user-123',
      email: 'a@example.com',
      groups: ['admin'],
    });
  });

  it('defaults groups to [] when cognito:groups is missing', async () => {
    mockVerify.mockResolvedValueOnce({ sub: 'u', email: 'e@x' });
    const req = { headers: { authorization: 'Bearer t' } } as Request;
    const res = mockRes();
    await requireAuth(req, res as Response, (() => undefined) as NextFunction);
    expect(req.user?.groups).toEqual([]);
  });
});

describe('optionalAuth', () => {
  beforeEach(() => {
    _resetVerifierForTests();
    mockVerify.mockReset();
    config.cognito.userPoolId = 'us-east-1_TEST';
    config.cognito.userPoolClientId = 'test-client-id';
  });

  it('calls next without setting req.user when no token is present', async () => {
    const req = { headers: {} } as Request;
    const res = mockRes();
    let nextCalled = false;
    await optionalAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(nextCalled).toBe(true);
    expect(req.user).toBeUndefined();
  });

  it('sets req.user when token is valid', async () => {
    mockVerify.mockResolvedValueOnce({ sub: 's', email: 'e@x' });
    const req = { headers: { authorization: 'Bearer ok' } } as Request;
    const res = mockRes();
    let nextCalled = false;
    await optionalAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(nextCalled).toBe(true);
    expect(req.user?.sub).toBe('s');
  });

  it('still calls next (and leaves req.user undefined) on a bad token', async () => {
    mockVerify.mockRejectedValueOnce(new Error('bad'));
    const req = { headers: { authorization: 'Bearer bad' } } as Request;
    const res = mockRes();
    let nextCalled = false;
    await optionalAuth(req, res as Response, (() => { nextCalled = true; }) as NextFunction);

    expect(nextCalled).toBe(true);
    expect(req.user).toBeUndefined();
  });
});

describe('requireGroup', () => {
  function mockNext(): { fn: NextFunction; called: () => boolean } {
    let was = false;
    return {
      fn: (() => { was = true; }) as NextFunction,
      called: () => was,
    };
  }

  it('401s when req.user is missing', () => {
    const guard = requireGroup('admin');
    const req = {} as Request;
    const res = mockRes();
    const next = mockNext();
    guard(req, res as Response, next.fn);
    expect(res._status).toBe(401);
    expect(next.called()).toBe(false);
  });

  it('403s when user is not in the group', () => {
    const guard = requireGroup('admin');
    const req = { user: { sub: 'u', email: 'e@x', groups: ['viewer'] } } as Request;
    const res = mockRes();
    const next = mockNext();
    guard(req, res as Response, next.fn);
    expect(res._status).toBe(403);
    expect(next.called()).toBe(false);
  });

  it('passes through when user has the group', () => {
    const guard = requireGroup('admin');
    const req = { user: { sub: 'u', email: 'e@x', groups: ['admin', 'viewer'] } } as Request;
    const res = mockRes();
    const next = mockNext();
    guard(req, res as Response, next.fn);
    expect(next.called()).toBe(true);
    expect(res._status).toBe(0);
  });
});
