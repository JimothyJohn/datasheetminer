/**
 * adminOnly middleware: blocks when APP_MODE !== 'admin'.
 *
 * config/index.ts reads APP_MODE from env at module load, so we re-import
 * the middleware with different env values per test via jest.isolateModules.
 */

import { Request, Response, NextFunction } from 'express';

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
  const originalAppMode = process.env.APP_MODE;

  afterEach(() => {
    if (originalAppMode === undefined) delete process.env.APP_MODE;
    else process.env.APP_MODE = originalAppMode;
  });

  it('allows requests when APP_MODE=admin', async () => {
    process.env.APP_MODE = 'admin';
    let nextCalled = false;
    const next: NextFunction = () => {
      nextCalled = true;
    };
    await jest.isolateModulesAsync(async () => {
      const { adminOnly } = await import('../src/middleware/adminOnly');
      const req = {} as Request;
      const res = mockRes();
      adminOnly(req, res as Response, next);
      expect(nextCalled).toBe(true);
      expect(res._status).toBe(0);
    });
  });

  it('blocks requests with 403 when APP_MODE=public', async () => {
    process.env.APP_MODE = 'public';
    let nextCalled = false;
    const next: NextFunction = () => {
      nextCalled = true;
    };
    await jest.isolateModulesAsync(async () => {
      const { adminOnly } = await import('../src/middleware/adminOnly');
      const req = {} as Request;
      const res = mockRes();
      adminOnly(req, res as Response, next);
      expect(nextCalled).toBe(false);
      expect(res._status).toBe(403);
    });
  });
});
