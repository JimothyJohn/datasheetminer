/**
 * Edge tests for the adminOnly guard.
 *
 * This is the hard boundary between non-admin users and admin routes.
 * Phase 4: gating is on the verified Cognito 'admin' group, not on
 * an env flag. A forged header, suggestive cookie, or path trick must
 * not loosen it — only a valid JWT containing the admin group does.
 *
 * Note: in production, requireAuth runs before adminOnly and rejects
 * unauthenticated callers with 401. These tests exercise adminOnly in
 * isolation; the request shapes here mirror what would arrive *if*
 * requireAuth had populated (or failed to populate) req.user.
 */

import { Request, Response, NextFunction } from 'express';
import { adminOnly } from '../src/middleware/adminOnly';

function mockReq(overrides: Partial<Request> = {}): Partial<Request> {
  return {
    method: 'GET',
    path: '/admin/blacklist',
    headers: {},
    ...overrides,
  };
}

function mockRes(): Partial<Response> & { _status: number; _body: any } {
  const res: any = {
    _status: 0,
    _body: null,
    status(code: number) {
      res._status = code;
      return res;
    },
    json(body: any) {
      res._body = body;
      return res;
    },
  };
  return res;
}

describe('adminOnly without req.user — 401 regardless of request shape', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  beforeEach(() => {
    nextCalled = false;
  });

  it('401 on GET', () => {
    const res = mockRes();
    adminOnly(mockReq({ method: 'GET' }) as Request, res as Response, next);
    expect(res._status).toBe(401);
    expect(nextCalled).toBe(false);
  });

  it('401 on POST', () => {
    const res = mockRes();
    adminOnly(mockReq({ method: 'POST' }) as Request, res as Response, next);
    expect(res._status).toBe(401);
    expect(nextCalled).toBe(false);
  });

  it.each([
    { Authorization: 'Bearer admin.jwt.forged' },
    { 'x-admin-token': 'hunter2' },
    { cookie: 'session=admin' },
    { 'x-forwarded-user': 'root' },
    { 'x-api-key': 'dsm_live_forged' },
  ])('401 with suggestive header %s — adminOnly does not consult headers', (headers) => {
    const res = mockRes();
    adminOnly(
      mockReq({ headers: headers as any }) as Request,
      res as Response,
      next,
    );
    expect(res._status).toBe(401);
    expect(nextCalled).toBe(false);
  });

  it('401 for every variant path under /admin/...', () => {
    const paths = [
      '/admin',
      '/admin/',
      '/admin/blacklist',
      '/admin/datasheets',
      '/admin/purge',
      '/admin/../products',
      '/admin/%00',
    ];
    for (const path of paths) {
      const res = mockRes();
      adminOnly(mockReq({ path }) as Request, res as Response, next);
      expect(res._status).toBe(401);
      expect(nextCalled).toBe(false);
    }
  });
});

describe('adminOnly with non-admin req.user — 403 regardless of request shape', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };
  const nonAdmin = { user: { sub: 'u', email: 'u@x', groups: ['viewer'] } };

  beforeEach(() => {
    nextCalled = false;
  });

  it('403 on GET with non-admin user', () => {
    const res = mockRes();
    adminOnly(mockReq({ method: 'GET', ...nonAdmin }) as Request, res as Response, next);
    expect(res._status).toBe(403);
    expect(nextCalled).toBe(false);
  });

  it('403 body does not leak appMode or config internals', () => {
    const res = mockRes();
    adminOnly(mockReq(nonAdmin) as Request, res as Response, next);
    const body = JSON.stringify(res._body);
    expect(body).not.toMatch(/appMode/i);
    expect(body).not.toMatch(/env/i);
  });

  it('forged groups in headers cannot promote a non-admin user', () => {
    const res = mockRes();
    adminOnly(
      mockReq({
        ...nonAdmin,
        headers: { 'x-cognito-groups': 'admin' } as any,
      }) as Request,
      res as Response,
      next,
    );
    expect(res._status).toBe(403);
    expect(nextCalled).toBe(false);
  });
});

describe('adminOnly with admin req.user — passes through', () => {
  it('next() called regardless of path or headers', () => {
    let nextCalled = false;
    const next: NextFunction = () => { nextCalled = true; };
    const res = mockRes();
    adminOnly(
      mockReq({
        path: '/admin/anything',
        headers: {},
        user: { sub: 'u', email: 'u@x', groups: ['admin', 'viewer'] },
      }) as Request,
      res as Response,
      next,
    );
    expect(nextCalled).toBe(true);
    expect(res._status).toBe(0);
  });
});
