/**
 * Admin-only middleware — 403 unless APP_MODE === 'admin'.
 *
 * Applied to /api/admin/* so admin routes are completely invisible on
 * deployed public instances. The readonly middleware would already block
 * writes, but we want GETs blocked too — the blacklist is an internal
 * concern and shouldn't be readable from a public deployment.
 */

import { Request, Response, NextFunction } from 'express';
import config from '../config';

export function adminOnly(_req: Request, res: Response, next: NextFunction): void {
  if (config.appMode !== 'admin') {
    res.status(403).json({
      success: false,
      error: 'Admin endpoints are disabled on this deployment',
    });
    return;
  }
  next();
}
