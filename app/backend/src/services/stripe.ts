/**
 * Stripe Lambda client - communicates with the Rust payments Lambda
 */

import config from '../config';

interface SubscriptionStatus {
  user_id: string;
  subscription_status: string;
  stripe_customer_id?: string;
  subscription_id?: string;
}

interface CheckoutResponse {
  checkout_url: string;
}

interface UsageResponse {
  reported: boolean;
  tokens: number;
}

class StripeService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = config.stripe.lambdaUrl;
  }

  private get enabled(): boolean {
    return !!this.baseUrl;
  }

  /**
   * Check if a user has an active subscription.
   * Returns null if Stripe is not configured (allows passthrough).
   */
  async getSubscriptionStatus(userId: string): Promise<SubscriptionStatus | null> {
    if (!this.enabled) return null;

    const res = await fetch(`${this.baseUrl}/status/${userId}`);
    if (!res.ok) {
      throw new Error(`Stripe status check failed: ${res.status}`);
    }
    return (await res.json()) as SubscriptionStatus;
  }

  /**
   * Check if user has an active or trialing subscription.
   * Returns true if Stripe is not configured (no billing enforcement).
   */
  async isSubscriptionActive(userId: string): Promise<boolean> {
    if (!this.enabled) return true;

    try {
      const status = await this.getSubscriptionStatus(userId);
      if (!status) return true;
      return status.subscription_status === 'active' || status.subscription_status === 'trialing';
    } catch (e) {
      console.error('Failed to check subscription status:', e);
      // Fail open if the billing service is down
      return true;
    }
  }

  /**
   * Create a checkout session for a user.
   */
  async createCheckoutSession(userId: string): Promise<CheckoutResponse> {
    if (!this.enabled) {
      throw new Error('Stripe billing is not configured');
    }

    const res = await fetch(`${this.baseUrl}/checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' })) as any;
      throw new Error(err.error || `Checkout failed: ${res.status}`);
    }

    return (await res.json()) as CheckoutResponse;
  }

  /**
   * Report token usage for a user after an API operation (e.g., scraping).
   */
  async reportUsage(userId: string, tokens: number): Promise<UsageResponse | null> {
    if (!this.enabled) return null;

    try {
      const res = await fetch(`${this.baseUrl}/usage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, tokens }),
      });

      if (!res.ok) {
        console.error(`Usage reporting failed: ${res.status}`);
        return null;
      }

      return (await res.json()) as UsageResponse;
    } catch (e) {
      // Usage reporting failure should not block the user
      console.error('Failed to report usage:', e);
      return null;
    }
  }
}

export const stripeService = new StripeService();
