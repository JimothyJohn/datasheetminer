/**
 * Middleware to gate endpoints behind an active Stripe subscription.
 * If STRIPE_LAMBDA_URL is not set, all requests pass through (no billing enforcement).
 */

import { Request, Response, NextFunction } from 'express';
import { stripeService } from '../services/stripe';

export async function requireSubscription(req: Request, res: Response, next: NextFunction): Promise<void> {
  // User ID comes from a header (set by your auth layer) or query param
  const userId = req.headers['x-user-id'] as string || req.query.user_id as string;

  if (!userId) {
    res.status(401).json({
      success: false,
      error: 'Missing user ID. Set x-user-id header or user_id query parameter.',
    });
    return;
  }

  const active = await stripeService.isSubscriptionActive(userId);

  if (!active) {
    res.status(403).json({
      success: false,
      error: 'Active subscription required. Please subscribe at /api/subscription/checkout.',
    });
    return;
  }

  // Attach userId to request for downstream usage reporting
  (req as any).userId = userId;
  next();
}
