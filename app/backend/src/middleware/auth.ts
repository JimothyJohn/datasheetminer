/**
 * JWT auth middleware backed by Cognito.
 *
 * `requireAuth`  — 401 unless a valid Cognito ID token is in the
 *                  Authorization header. Attaches `req.user`.
 * `optionalAuth` — same verify, but missing token is fine (user stays
 *                  undefined). Used on read endpoints that personalize
 *                  if signed in but don't require it.
 * `requireGroup` — 403 unless the authed user is in the named group.
 *                  Stack after `requireAuth`.
 *
 * Verifier is lazily constructed so config can be filled in by
 * `loadSsmSecrets()` after module load (Lambda cold start path). If
 * Cognito IDs aren't available at all, every authed request fails 503
 * — preferable to a noisy "auth disabled" mode that silently lets
 * everyone through.
 */

import { Request, Response, NextFunction } from 'express';
import { CognitoJwtVerifier } from 'aws-jwt-verify';
import config from '../config';

export interface AuthedUser {
  sub: string;
  email: string;
  groups: string[];
}

declare module 'express-serve-static-core' {
  interface Request {
    user?: AuthedUser;
  }
}

type Verifier = ReturnType<typeof CognitoJwtVerifier.create<{
  userPoolId: string;
  tokenUse: 'id';
  clientId: string;
}>>;

let cachedVerifier: Verifier | null = null;

function getVerifier(): Verifier | null {
  if (cachedVerifier) return cachedVerifier;
  if (!config.cognito.userPoolId || !config.cognito.userPoolClientId) {
    return null;
  }
  cachedVerifier = CognitoJwtVerifier.create({
    userPoolId: config.cognito.userPoolId,
    tokenUse: 'id',
    clientId: config.cognito.userPoolClientId,
  });
  return cachedVerifier;
}

function extractBearer(req: Request): string | null {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) return null;
  const token = header.slice('Bearer '.length).trim();
  return token || null;
}

async function verifyToken(token: string): Promise<AuthedUser | null> {
  const verifier = getVerifier();
  if (!verifier) return null;
  const payload = await verifier.verify(token);
  return {
    sub: payload.sub,
    email: (payload.email as string) || '',
    groups: (payload['cognito:groups'] as string[]) || [],
  };
}

export async function requireAuth(req: Request, res: Response, next: NextFunction): Promise<void> {
  if (!getVerifier()) {
    res.status(503).json({
      success: false,
      error: 'Auth not configured on this deployment',
    });
    return;
  }
  const token = extractBearer(req);
  if (!token) {
    res.status(401).json({ success: false, error: 'Missing bearer token' });
    return;
  }
  try {
    const user = await verifyToken(token);
    if (!user) {
      res.status(503).json({ success: false, error: 'Auth not configured' });
      return;
    }
    req.user = user;
    next();
  } catch (err) {
    console.warn('[auth] token verify failed:', (err as Error).message);
    res.status(401).json({ success: false, error: 'Invalid or expired token' });
  }
}

export async function optionalAuth(req: Request, _res: Response, next: NextFunction): Promise<void> {
  const token = extractBearer(req);
  if (!token) {
    next();
    return;
  }
  try {
    const user = await verifyToken(token);
    if (user) req.user = user;
  } catch {
    // best-effort — failed verify means we treat the caller as unauthed
  }
  next();
}

export function requireGroup(group: string) {
  return function groupGuard(req: Request, res: Response, next: NextFunction): void {
    if (!req.user) {
      res.status(401).json({ success: false, error: 'Authentication required' });
      return;
    }
    if (!req.user.groups.includes(group)) {
      res.status(403).json({ success: false, error: `Group '${group}' required` });
      return;
    }
    next();
  };
}

// Test hook — clears the cached verifier so subsequent calls re-read
// config. Production code never needs this.
export function _resetVerifierForTests(): void {
  cachedVerifier = null;
}
