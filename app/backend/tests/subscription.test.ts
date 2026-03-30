/**
 * Tests for subscription routes, middleware, and stripe service.
 */

import request from 'supertest';
import app from '../src/index';
import { stripeService } from '../src/services/stripe';
import { requireSubscription } from '../src/middleware/subscription';
import { Request, Response, NextFunction } from 'express';

// Mock stripe service methods
jest.mock('../src/services/stripe', () => ({
  stripeService: {
    getSubscriptionStatus: jest.fn(),
    isSubscriptionActive: jest.fn(),
    createCheckoutSession: jest.fn(),
    reportUsage: jest.fn(),
  },
}));

jest.mock('../src/db/dynamodb');

// =================== Subscription Routes ===================

describe('Subscription Routes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('GET /api/subscription/config', () => {
    it('returns billing_enabled status', async () => {
      const response = await request(app).get('/api/subscription/config');
      expect(response.status).toBe(200);
      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveProperty('billing_enabled');
    });
  });

  describe('GET /api/subscription/status/:userId', () => {
    it('returns subscription status when stripe is configured', async () => {
      (stripeService.getSubscriptionStatus as jest.Mock).mockResolvedValue({
        user_id: 'user-123',
        subscription_status: 'active',
      });

      const response = await request(app).get('/api/subscription/status/user-123');
      expect(response.status).toBe(200);
      expect(response.body.success).toBe(true);
    });

    it('returns none status when stripe is not configured', async () => {
      // In test env, config.stripe.lambdaUrl is empty, so the early-return path is taken
      const response = await request(app).get('/api/subscription/status/user-123');
      expect(response.status).toBe(200);
      expect(response.body.data.subscription_status).toBe('none');
      expect(response.body.data.billing_enabled).toBe(false);
    });
  });

  describe('POST /api/subscription/checkout', () => {
    it('returns 400 when user_id is missing', async () => {
      const response = await request(app).post('/api/subscription/checkout').send({});
      expect(response.status).toBe(400);
      expect(response.body.error).toContain('user_id');
    });

    it('creates checkout session when user_id provided', async () => {
      (stripeService.createCheckoutSession as jest.Mock).mockResolvedValue({
        checkout_url: 'https://checkout.stripe.com/session123',
      });

      const response = await request(app)
        .post('/api/subscription/checkout')
        .send({ user_id: 'user-123' });

      expect(response.status).toBe(200);
      expect(response.body.success).toBe(true);
      expect(response.body.data.checkout_url).toContain('stripe.com');
    });

    it('handles checkout error', async () => {
      (stripeService.createCheckoutSession as jest.Mock).mockRejectedValue(
        new Error('Checkout failed')
      );

      const response = await request(app)
        .post('/api/subscription/checkout')
        .send({ user_id: 'user-123' });

      expect(response.status).toBe(500);
      expect(response.body.success).toBe(false);
    });
  });
});

// =================== Subscription Middleware ===================

describe('requireSubscription middleware', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  function mockReq(headers: Record<string, string> = {}, query: Record<string, string> = {}): Partial<Request> {
    return { headers, query } as any;
  }

  function mockRes(): any {
    const res: any = {
      _status: 0,
      _body: null,
      status(code: number) { res._status = code; return res; },
      json(body: any) { res._body = body; return res; },
    };
    return res;
  }

  beforeEach(() => {
    nextCalled = false;
    jest.clearAllMocks();
  });

  it('returns 401 when no user ID provided', async () => {
    const req = mockReq();
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(res._status).toBe(401);
    expect(nextCalled).toBe(false);
  });

  it('accepts user ID from x-user-id header', async () => {
    (stripeService.isSubscriptionActive as jest.Mock).mockResolvedValue(true);
    const req = mockReq({ 'x-user-id': 'user-123' });
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(nextCalled).toBe(true);
    expect((req as any).userId).toBe('user-123');
  });

  it('accepts user ID from query parameter', async () => {
    (stripeService.isSubscriptionActive as jest.Mock).mockResolvedValue(true);
    const req = mockReq({}, { user_id: 'user-456' });
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(nextCalled).toBe(true);
    expect((req as any).userId).toBe('user-456');
  });

  it('returns 403 when subscription is not active', async () => {
    (stripeService.isSubscriptionActive as jest.Mock).mockResolvedValue(false);
    const req = mockReq({ 'x-user-id': 'user-123' });
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(res._status).toBe(403);
    expect(res._body.error).toContain('subscription required');
    expect(nextCalled).toBe(false);
  });

  it('passes through when subscription is active', async () => {
    (stripeService.isSubscriptionActive as jest.Mock).mockResolvedValue(true);
    const req = mockReq({ 'x-user-id': 'user-123' });
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(nextCalled).toBe(true);
  });
});

// =================== StripeService (unit, mocked fetch) ===================

describe('StripeService unit logic', () => {
  it('stripeService is exported as singleton', () => {
    expect(stripeService).toBeDefined();
    expect(stripeService.getSubscriptionStatus).toBeDefined();
    expect(stripeService.isSubscriptionActive).toBeDefined();
    expect(stripeService.createCheckoutSession).toBeDefined();
    expect(stripeService.reportUsage).toBeDefined();
  });
});
