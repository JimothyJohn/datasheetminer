/**
 * Tests for subscription routes, middleware, and stripe service.
 *
 * Phase 4: routes are now requireAuth-gated; identity comes from
 * req.user.sub (the JWT). Tests mock aws-jwt-verify the same way
 * auth.middleware.test.ts does and supply a Bearer header.
 */

import request from 'supertest';
import { Request, Response, NextFunction } from 'express';

const mockVerify = jest.fn();
jest.mock('aws-jwt-verify', () => ({
  CognitoJwtVerifier: { create: jest.fn(() => ({ verify: mockVerify })) },
}));

import app from '../src/index';
import config from '../src/config';
import { stripeService } from '../src/services/stripe';
import { requireSubscription } from '../src/middleware/subscription';
import { _resetVerifierForTests } from '../src/middleware/auth';

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
  const origPoolId = config.cognito.userPoolId;
  const origClientId = config.cognito.userPoolClientId;

  beforeEach(() => {
    jest.clearAllMocks();
    _resetVerifierForTests();
    mockVerify.mockReset();
    config.cognito.userPoolId = 'us-east-1_TEST';
    config.cognito.userPoolClientId = 'test-client-id';
  });

  afterAll(() => {
    config.cognito.userPoolId = origPoolId;
    config.cognito.userPoolClientId = origClientId;
  });

  function authedUser(sub = 'user-123', groups: string[] = []) {
    mockVerify.mockResolvedValue({
      sub,
      email: `${sub}@example.com`,
      'cognito:groups': groups,
    });
  }

  describe('GET /api/subscription/config', () => {
    it('returns billing_enabled status without auth (public endpoint)', async () => {
      const response = await request(app).get('/api/subscription/config');
      expect(response.status).toBe(200);
      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveProperty('billing_enabled');
    });
  });

  describe('GET /api/subscription/status', () => {
    it('returns 401 without an auth token', async () => {
      const response = await request(app).get('/api/subscription/status');
      expect(response.status).toBe(401);
    });

    it('returns subscription status when stripe is configured', async () => {
      authedUser('user-123');
      const origUrl = config.stripe.lambdaUrl;
      config.stripe.lambdaUrl = 'https://stripe-lambda.test';
      try {
        (stripeService.getSubscriptionStatus as jest.Mock).mockResolvedValue({
          user_id: 'user-123',
          subscription_status: 'active',
        });

        const response = await request(app)
          .get('/api/subscription/status')
          .set('Authorization', 'Bearer good-token');
        expect(response.status).toBe(200);
        expect(response.body.success).toBe(true);
        expect(stripeService.getSubscriptionStatus).toHaveBeenCalledWith('user-123');
      } finally {
        config.stripe.lambdaUrl = origUrl;
      }
    });

    it('returns none status when stripe is not configured', async () => {
      authedUser('user-123');
      // In test env, config.stripe.lambdaUrl is empty → early-return path
      const response = await request(app)
        .get('/api/subscription/status')
        .set('Authorization', 'Bearer good-token');
      expect(response.status).toBe(200);
      expect(response.body.data.subscription_status).toBe('none');
      expect(response.body.data.billing_enabled).toBe(false);
    });
  });

  describe('POST /api/subscription/checkout', () => {
    it('returns 401 without an auth token', async () => {
      const response = await request(app).post('/api/subscription/checkout').send({});
      expect(response.status).toBe(401);
    });

    it('rejects legacy body with user_id field (must use auth token)', async () => {
      authedUser('user-123');
      const response = await request(app)
        .post('/api/subscription/checkout')
        .set('Authorization', 'Bearer good-token')
        .send({ user_id: 'someone-else' });
      expect(response.status).toBe(400);
      expect(response.body.error).toMatch(/empty|auth token/i);
    });

    it('creates checkout session using authed sub', async () => {
      authedUser('user-123');
      (stripeService.createCheckoutSession as jest.Mock).mockResolvedValue({
        checkout_url: 'https://checkout.stripe.com/session123',
      });

      const response = await request(app)
        .post('/api/subscription/checkout')
        .set('Authorization', 'Bearer good-token')
        .send({});

      expect(response.status).toBe(200);
      expect(response.body.success).toBe(true);
      expect(response.body.data.checkout_url).toContain('stripe.com');
      expect(stripeService.createCheckoutSession).toHaveBeenCalledWith('user-123');
    });

    it('handles checkout error', async () => {
      authedUser('user-123');
      (stripeService.createCheckoutSession as jest.Mock).mockRejectedValue(
        new Error('Checkout failed'),
      );

      const response = await request(app)
        .post('/api/subscription/checkout')
        .set('Authorization', 'Bearer good-token')
        .send({});

      expect(response.status).toBe(500);
      expect(response.body.success).toBe(false);
    });
  });
});

// =================== Subscription Middleware ===================

describe('requireSubscription middleware', () => {
  let nextCalled: boolean;
  const next: NextFunction = () => { nextCalled = true; };

  function reqWithUser(sub: string | null): Partial<Request> {
    if (sub === null) return {} as Partial<Request>;
    return { user: { sub, email: `${sub}@example.com`, groups: [] } } as Partial<Request>;
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

  it('returns 401 when req.user is not set (auth middleware skipped)', async () => {
    const req = reqWithUser(null);
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(res._status).toBe(401);
    expect(res._body.error).toContain('Authentication required');
    expect(nextCalled).toBe(false);
  });

  it('returns 403 when subscription is not active', async () => {
    (stripeService.isSubscriptionActive as jest.Mock).mockResolvedValue(false);
    const req = reqWithUser('user-123');
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(res._status).toBe(403);
    expect(res._body.error).toContain('subscription required');
    expect(nextCalled).toBe(false);
  });

  it('passes through when subscription is active and user is authed', async () => {
    (stripeService.isSubscriptionActive as jest.Mock).mockResolvedValue(true);
    const req = reqWithUser('user-123');
    const res = mockRes();

    await requireSubscription(req as Request, res as Response, next);
    expect(nextCalled).toBe(true);
    expect(stripeService.isSubscriptionActive).toHaveBeenCalledWith('user-123');
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
