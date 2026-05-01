/**
 * Admin-only middleware — 403 unless the authed user is in the
 * Cognito 'admin' group.
 *
 * Stack `requireAuth` before this so req.user is populated. Applied to
 * /api/admin/* so admin routes are completely invisible to
 * unauthenticated callers and non-admin users — the blacklist is an
 * internal concern and shouldn't be readable from a public deployment.
 *
 * Replaces the old `config.appMode === 'admin'` env-toggle gate. With
 * Cognito groups in place, one deployed environment can serve both
 * admin and public UIs based on token contents.
 */

import { Request, Response, NextFunction } from 'express';

export function adminOnly(req: Request, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({
      success: false,
      error: 'Authentication required',
    });
    return;
  }
  if (!req.user.groups.includes('admin')) {
    res.status(403).json({
      success: false,
      error: 'Admin group membership required',
    });
    return;
  }
  next();
}
