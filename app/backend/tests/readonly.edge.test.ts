/**
 * Edge cases for the readonly middleware that existing readonly.test.ts
 * doesn't cover. The allowlist is a `Set` lookup on exact `req.path`, which
 * means any path normalization drift could silently widen the exemption.
 */

import { readonlyGuard } from '../src/middleware/readonly';
import { Request, Response, NextFunction } from 'express';

function mockReq(method: string, path: string): Partial<Request> {
  return { method, path };
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

describe('readonlyGuard — exemption is exact-match, not prefix', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  beforeEach(() => { nextCalled = false; });

  it.each([
    '/upload/extra',
    '/upload/foo',
    '/uploadd',
    '/upload.json',
    '/upload?x=1',
    '/Upload',
    '/UPLOAD',
    '//upload',
  ])('POST %s is blocked (not in exact-match allowlist)', (path) => {
    const req = mockReq('POST', path);
    const res = mockRes();
    readonlyGuard(req as Request, res as Response, next);
    expect(nextCalled).toBe(false);
    expect(res._status).toBe(403);
  });
});

describe('readonlyGuard — unusual HTTP verbs', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  beforeEach(() => { nextCalled = false; });

  it.each(['PATCH', 'CONNECT', 'TRACE', 'PROPFIND', 'LOCK'])(
    '%s on /products is blocked',
    (method) => {
      const req = mockReq(method, '/products');
      const res = mockRes();
      readonlyGuard(req as Request, res as Response, next);
      expect(nextCalled).toBe(false);
      expect(res._status).toBe(403);
    },
  );
});

describe('readonlyGuard — admin paths are never exempt', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  beforeEach(() => { nextCalled = false; });

  it.each(['POST', 'PUT', 'DELETE'])(
    '%s /admin/blacklist is blocked',
    (method) => {
      const req = mockReq(method, '/admin/blacklist');
      const res = mockRes();
      readonlyGuard(req as Request, res as Response, next);
      expect(nextCalled).toBe(false);
      expect(res._status).toBe(403);
    },
  );
});

describe('readonlyGuard — response shape', () => {
  const next: NextFunction = () => {};

  it('403 body includes success: false and a hint field', () => {
    const req = mockReq('POST', '/products');
    const res = mockRes();
    readonlyGuard(req as Request, res as Response, next);
    expect(res._status).toBe(403);
    expect(res._body).toMatchObject({ success: false });
    expect(res._body.hint).toBeDefined();
  });

  it('403 body does not include a stack trace or internal path', () => {
    const req = mockReq('POST', '/products');
    const res = mockRes();
    readonlyGuard(req as Request, res as Response, next);
    const serialized = JSON.stringify(res._body);
    expect(serialized).not.toMatch(/readonly\.ts/);
    expect(serialized).not.toMatch(/at \S+/);
  });
});
