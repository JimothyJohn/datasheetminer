/**
 * Middleware to gate endpoints behind an active Stripe subscription.
 *
 * Stack as: requireAuth → requireSubscription. The auth middleware
 * verifies the bearer token and attaches `req.user`; this middleware
 * trusts that and uses `req.user.sub` as the Stripe customer ID.
 *
 * Previous version trusted an `x-user-id` header without verification —
 * any client could impersonate any user. That was safe only because no
 * route used the middleware; do not reintroduce that pattern.
 */

import { Request, Response, NextFunction } from 'express';
import { stripeService } from '../services/stripe';

export async function requireSubscription(req: Request, res: Response, next: NextFunction): Promise<void> {
  if (!req.user) {
    res.status(401).json({
      success: false,
      error: 'Authentication required (stack requireAuth before requireSubscription)',
    });
    return;
  }

  const active = await stripeService.isSubscriptionActive(req.user.sub);

  if (!active) {
    res.status(403).json({
      success: false,
      error: 'Active subscription required. Please subscribe at /api/subscription/checkout.',
    });
    return;
  }

  next();
}
