/**
 * Readonly middleware — enforces read-only access in public mode.
 *
 * When APP_MODE=public, all non-GET/HEAD/OPTIONS requests are rejected
 * with 403. This is the hard boundary between the public cloud deployment
 * and the local admin toolset.
 */

import { Request, Response, NextFunction } from 'express';

const ALLOWED_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export function readonlyGuard(req: Request, res: Response, next: NextFunction): void {
  if (ALLOWED_METHODS.has(req.method)) {
    next();
    return;
  }

  console.warn(`[readonly] Blocked ${req.method} ${req.path} — public mode is read-only`);
  res.status(403).json({
    success: false,
    error: 'This endpoint is read-only in public mode',
    hint: 'Use the local admin toolset for write operations',
  });
}
