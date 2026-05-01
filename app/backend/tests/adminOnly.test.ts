/**
 * adminOnly middleware: Cognito-group based gate.
 *
 * Phase 4: replaced the old `config.appMode === 'admin'` env-toggle.
 * The middleware now reads req.user (populated by requireAuth) and
 * checks for 'admin' group membership.
 */

import { Request, Response, NextFunction } from 'express';
import { adminOnly } from '../src/middleware/adminOnly';

function mockRes(): Partial<Response> & { _status: number; _body: unknown } {
  const res: Partial<Response> & { _status: number; _body: unknown } = {
    _status: 0,
    _body: null,
    status(this: typeof res, code: number) {
      this._status = code;
      return this as Response;
    },
    json(this: typeof res, body: unknown) {
      this._body = body;
      return this as Response;
    },
  };
  return res;
}

describe('adminOnly middleware', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  beforeEach(() => {
    nextCalled = false;
  });

  it('allows requests when req.user is in the admin group', () => {
    const req = {
      user: { sub: 'u-1', email: 'u@x', groups: ['admin'] },
    } as Request;
    const res = mockRes();
    adminOnly(req, res as Response, next);
    expect(nextCalled).toBe(true);
    expect(res._status).toBe(0);
  });

  it('returns 401 when req.user is missing (auth middleware skipped)', () => {
    const req = {} as Request;
    const res = mockRes();
    adminOnly(req, res as Response, next);
    expect(nextCalled).toBe(false);
    expect(res._status).toBe(401);
  });

  it('returns 403 when authed user lacks the admin group', () => {
    const req = {
      user: { sub: 'u-1', email: 'u@x', groups: ['viewer'] },
    } as Request;
    const res = mockRes();
    adminOnly(req, res as Response, next);
    expect(nextCalled).toBe(false);
    expect(res._status).toBe(403);
  });

  it('returns 403 when user has empty groups array', () => {
    const req = {
      user: { sub: 'u-1', email: 'u@x', groups: [] as string[] },
    } as Request;
    const res = mockRes();
    adminOnly(req, res as Response, next);
    expect(nextCalled).toBe(false);
    expect(res._status).toBe(403);
  });
});
