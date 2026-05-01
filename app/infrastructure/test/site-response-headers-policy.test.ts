/**
 * SiteResponseHeadersPolicy synth assertions.
 *
 * Verifies that the policy emits the directives we actually want
 * (script-src 'self' is the load-bearing one for localStorage-token
 * SPAs) and that the other security headers ride along.
 */

import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { SiteResponseHeadersPolicy } from '../lib/headers/site-response-headers-policy';

function templateFor(props: ConstructorParameters<typeof SiteResponseHeadersPolicy>[2]): Template {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, 'TestPolicyHost', {
    env: { account: '111111111111', region: 'us-east-1' },
  });
  new SiteResponseHeadersPolicy(stack, 'TestPolicy', props);
  return Template.fromStack(stack);
}

function getCsp(t: Template): string {
  const policy = Object.values(t.toJSON().Resources).find(
    (r: any) => r.Type === 'AWS::CloudFront::ResponseHeadersPolicy',
  ) as any;
  return policy.Properties.ResponseHeadersPolicyConfig.SecurityHeadersConfig
    .ContentSecurityPolicy.ContentSecurityPolicy;
}

describe('SiteResponseHeadersPolicy', () => {
  it('creates a stage-named ResponseHeadersPolicy', () => {
    const t = templateFor({ stage: 'staging' });
    t.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
      ResponseHeadersPolicyConfig: Match.objectLike({
        Name: 'specodex-staging-security-headers',
      }),
    });
  });

  describe('CSP directives (default)', () => {
    let csp: string;
    beforeAll(() => {
      csp = getCsp(templateFor({ stage: 'staging' }));
    });

    it("blocks third-party scripts via script-src 'self'", () => {
      expect(csp).toMatch(/script-src 'self'(?! \S)/);
    });

    it("forbids inline + eval scripts (no unsafe-* in script-src)", () => {
      // The negative case is what protects localStorage tokens.
      const scriptSrc = csp.split(';').find(d => d.trim().startsWith('script-src'));
      expect(scriptSrc).toBeDefined();
      expect(scriptSrc).not.toMatch(/'unsafe-inline'/);
      expect(scriptSrc).not.toMatch(/'unsafe-eval'/);
    });

    it("permits inline styles (acknowledged tradeoff with React inline styles)", () => {
      expect(csp).toMatch(/style-src 'self' 'unsafe-inline'/);
    });

    it("forbids embedding in iframes via frame-ancestors 'none'", () => {
      expect(csp).toMatch(/frame-ancestors 'none'/);
    });

    it('allows data: and https: image sources', () => {
      expect(csp).toMatch(/img-src [^;]*data:/);
      expect(csp).toMatch(/img-src [^;]*https:/);
    });

    it('blocks plugin embeds via object-src none', () => {
      expect(csp).toMatch(/object-src 'none'/);
    });

    it('upgrades any mixed-content references', () => {
      expect(csp).toMatch(/upgrade-insecure-requests/);
    });
  });

  it('respects a contentSecurityPolicy override', () => {
    const t = templateFor({
      stage: 'staging',
      contentSecurityPolicy: "default-src 'self'; script-src 'self' 'nonce-abc'",
    });
    expect(getCsp(t)).toBe("default-src 'self'; script-src 'self' 'nonce-abc'");
  });

  it('disables CSP when override is empty string (debug escape hatch)', () => {
    const t = templateFor({ stage: 'staging', contentSecurityPolicy: '' });
    const policy = Object.values(t.toJSON().Resources).find(
      (r: any) => r.Type === 'AWS::CloudFront::ResponseHeadersPolicy',
    ) as any;
    expect(policy.Properties.ResponseHeadersPolicyConfig.SecurityHeadersConfig
      .ContentSecurityPolicy).toBeUndefined();
    // Other headers still ship
    expect(policy.Properties.ResponseHeadersPolicyConfig.SecurityHeadersConfig
      .StrictTransportSecurity).toBeDefined();
  });

  it('ships HSTS for 1 year with includeSubdomains', () => {
    const t = templateFor({ stage: 'staging' });
    t.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
      ResponseHeadersPolicyConfig: Match.objectLike({
        SecurityHeadersConfig: Match.objectLike({
          StrictTransportSecurity: {
            AccessControlMaxAgeSec: 31536000,   // 365 days
            IncludeSubdomains: true,
            Preload: false,
            Override: true,
          },
        }),
      }),
    });
  });

  it('sets X-Frame-Options DENY and X-Content-Type-Options nosniff', () => {
    const t = templateFor({ stage: 'staging' });
    t.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
      ResponseHeadersPolicyConfig: Match.objectLike({
        SecurityHeadersConfig: Match.objectLike({
          FrameOptions: { FrameOption: 'DENY', Override: true },
          ContentTypeOptions: { Override: true },
        }),
      }),
    });
  });

  it('sets a strict referrer policy', () => {
    const t = templateFor({ stage: 'staging' });
    t.hasResourceProperties('AWS::CloudFront::ResponseHeadersPolicy', {
      ResponseHeadersPolicyConfig: Match.objectLike({
        SecurityHeadersConfig: Match.objectLike({
          ReferrerPolicy: {
            ReferrerPolicy: 'strict-origin-when-cross-origin',
            Override: true,
          },
        }),
      }),
    });
  });
});
