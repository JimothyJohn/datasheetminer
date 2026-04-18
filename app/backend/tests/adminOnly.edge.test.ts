/**
 * Edge tests for the adminOnly guard.
 *
 * This is the hard boundary between public deployments and admin routes. A
 * forged header, a path trick, or a weird method must NOT loosen it — the
 * gate only opens when `config.appMode === 'admin'` at process start.
 *
 * config is captured at module load, so we re-import the middleware under
 * `APP_MODE=public` via jest.isolateModulesAsync — same pattern as the
 * existing adminOnly.test.ts.
 */

import { Request, Response, NextFunction } from 'express';

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

async function withPublicMode(
  fn: (adminOnly: (req: Request, res: Response, next: NextFunction) => void) => void,
): Promise<void> {
  const original = process.env.APP_MODE;
  process.env.APP_MODE = 'public';
  try {
    await jest.isolateModulesAsync(async () => {
      const { adminOnly } = await import('../src/middleware/adminOnly');
      fn(adminOnly);
    });
  } finally {
    if (original === undefined) delete process.env.APP_MODE;
    else process.env.APP_MODE = original;
  }
}

describe('adminOnly in public mode — ignores all request state', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => {
    nextCalled = true;
  };

  beforeEach(() => {
    nextCalled = false;
  });

  it('403 on GET', async () => {
    await withPublicMode((adminOnly) => {
      const res = mockRes();
      adminOnly(mockReq({ method: 'GET' }) as Request, res as Response, next);
      expect(res._status).toBe(403);
      expect(nextCalled).toBe(false);
    });
  });

  it('403 on POST', async () => {
    await withPublicMode((adminOnly) => {
      const res = mockRes();
      adminOnly(mockReq({ method: 'POST' }) as Request, res as Response, next);
      expect(res._status).toBe(403);
      expect(nextCalled).toBe(false);
    });
  });

  it.each([
    { Authorization: 'Bearer admin.jwt.forged' },
    { 'x-admin-token': 'hunter2' },
    { cookie: 'session=admin' },
    { 'x-forwarded-user': 'root' },
    { 'x-api-key': 'dsm_live_forged' },
  ])('403 with suggestive header %s', async (headers) => {
    await withPublicMode((adminOnly) => {
      const res = mockRes();
      adminOnly(
        mockReq({ headers: headers as any }) as Request,
        res as Response,
        next,
      );
      expect(res._status).toBe(403);
      expect(nextCalled).toBe(false);
    });
  });

  it('403 for every variant path under /admin/...', async () => {
    const paths = [
      '/admin',
      '/admin/',
      '/admin/blacklist',
      '/admin/datasheets',
      '/admin/purge',
      '/admin/../products',
      '/admin/%00',
    ];
    await withPublicMode((adminOnly) => {
      for (const path of paths) {
        const res = mockRes();
        adminOnly(mockReq({ path }) as Request, res as Response, next);
        expect(res._status).toBe(403);
        expect(nextCalled).toBe(false);
      }
    });
  });

  it('403 body does not leak appMode or config internals', async () => {
    await withPublicMode((adminOnly) => {
      const res = mockRes();
      adminOnly(mockReq() as Request, res as Response, next);
      const body = JSON.stringify(res._body);
      expect(body).not.toMatch(/appMode/i);
      expect(body).not.toMatch(/env/i);
    });
  });
});

describe('adminOnly in admin mode — passes through', () => {
  it('next() called regardless of path or headers', async () => {
    const original = process.env.APP_MODE;
    process.env.APP_MODE = 'admin';
    try {
      await jest.isolateModulesAsync(async () => {
        const { adminOnly } = await import('../src/middleware/adminOnly');
        let nextCalled = false;
        const next: NextFunction = () => {
          nextCalled = true;
        };
        const res = mockRes();
        adminOnly(
          mockReq({ path: '/admin/anything', headers: {} }) as Request,
          res as Response,
          next,
        );
        expect(nextCalled).toBe(true);
        expect(res._status).toBe(0);
      });
    } finally {
      if (original === undefined) delete process.env.APP_MODE;
      else process.env.APP_MODE = original;
    }
  });
});
