/**
 * API routes for subscription management.
 * Proxies requests to the Stripe payments Lambda.
 */

import { Router, Request, Response } from 'express';
import { stripeService } from '../services/stripe';
import config from '../config';

const router = Router();

/**
 * GET /api/subscription/status/:userId
 * Check subscription status for a user
 */
router.get('/status/:userId', async (req: Request, res: Response) => {
  try {
    if (!config.stripe.lambdaUrl) {
      res.json({
        success: true,
        data: { subscription_status: 'none', billing_enabled: false },
      });
      return;
    }

    const status = await stripeService.getSubscriptionStatus(req.params.userId);
    res.json({ success: true, data: status });
  } catch (error: any) {
    console.error('Error checking subscription status:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * POST /api/subscription/checkout
 * Create a Stripe checkout session
 * Body: { user_id: string }
 */
router.post('/checkout', async (req: Request, res: Response): Promise<void> => {
  try {
    const { user_id } = req.body;

    if (!user_id) {
      res.status(400).json({ success: false, error: 'user_id is required' });
      return;
    }

    const result = await stripeService.createCheckoutSession(user_id);
    res.json({ success: true, data: result });
  } catch (error: any) {
    console.error('Error creating checkout session:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * GET /api/subscription/config
 * Returns whether billing is enabled (useful for frontend conditional rendering)
 */
router.get('/config', (_req: Request, res: Response) => {
  res.json({
    success: true,
    data: {
      billing_enabled: !!config.stripe.lambdaUrl,
    },
  });
});

export default router;
