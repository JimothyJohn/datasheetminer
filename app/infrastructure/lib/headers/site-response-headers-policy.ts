/**
 * CloudFront ResponseHeadersPolicy for the SPA + /api/* behaviors
 * (todo/AUTH.md Phase 5 hardening — CSP).
 *
 * Why this matters for auth: id/access tokens live in localStorage
 * (Phase 3 tradeoff for CORS simplicity). That choice is acceptable
 * iff the page that reads them can't load attacker-controlled
 * scripts. CSP `script-src 'self'` is the load-bearing directive.
 *
 * Directive choices, with reasoning where non-obvious:
 *
 *   default-src 'self'
 *     Catch-all for anything not enumerated below.
 *
 *   script-src 'self'
 *     The point of all this. No 'unsafe-inline', no 'unsafe-eval',
 *     no third-party CDNs. If you ever add an analytics tag, hash
 *     or nonce it — don't open the gate.
 *
 *   style-src 'self' 'unsafe-inline'
 *     Required because the React tree has inline component styles
 *     today. Tightening this needs a refactor pass to extract
 *     styles to CSS Modules (out of scope for Phase 5).
 *
 *   img-src 'self' data: https:
 *     'data:' for inline SVG / base64 images. 'https:' because
 *     manufacturer datasheet thumbnails come from various CDNs;
 *     scoping per-vendor is more churn than benefit.
 *
 *   connect-src 'self'
 *     Same-origin only. Cognito calls go through our /api/auth/*
 *     proxy, not direct from the SPA, so we don't need
 *     cognito-idp.us-east-1.amazonaws.com here.
 *
 *   frame-ancestors 'none'
 *     Equivalent to X-Frame-Options DENY in modern browsers; both
 *     ship for older user agents.
 *
 *   base-uri 'self'
 *     Stops a script-injection foothold from changing the base URL.
 *
 *   form-action 'self'
 *     Same idea, for any <form action="..."> on the page.
 *
 *   object-src 'none'
 *     Blocks <embed>, <object>, <applet>. We have none; cheap
 *     defense-in-depth.
 *
 *   upgrade-insecure-requests
 *     CloudFront already redirects HTTP→HTTPS, but this catches
 *     mixed content from any origin we did link to.
 *
 * The other security headers (HSTS, X-Content-Type-Options,
 * X-Frame-Options, Referrer-Policy) ride along because there's no
 * good reason not to ship them and CDK groups them with CSP under
 * `securityHeadersBehavior`.
 */

import * as cdk from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import { Construct } from 'constructs';

const DEFAULT_CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  'upgrade-insecure-requests',
].join('; ');

export interface SiteResponseHeadersPolicyProps {
  /** Stage name; appears in the policy resource name so dev / staging /
   *  prod don't collide on the same Distribution if both deploy. */
  stage: string;
  /** Override the CSP directive string. Use sparingly — the default
   *  is the result of the tradeoff analysis in the file-top
   *  docstring. Empty string disables CSP entirely (escape hatch
   *  for debugging "is this CSP blocking my new feature?" without
   *  redeploying with a removed construct). */
  contentSecurityPolicy?: string;
}

export class SiteResponseHeadersPolicy extends Construct {
  public readonly policy: cloudfront.ResponseHeadersPolicy;

  constructor(scope: Construct, id: string, props: SiteResponseHeadersPolicyProps) {
    super(scope, id);

    const csp = props.contentSecurityPolicy ?? DEFAULT_CSP;

    this.policy = new cloudfront.ResponseHeadersPolicy(this, 'Policy', {
      responseHeadersPolicyName: `specodex-${props.stage}-security-headers`,
      comment: 'Specodex SPA + /api/* response headers (CSP, HSTS, frame-ancestors)',
      securityHeadersBehavior: {
        ...(csp
          ? {
              contentSecurityPolicy: {
                contentSecurityPolicy: csp,
                override: true,
              },
            }
          : {}),
        contentTypeOptions: { override: true },
        frameOptions: {
          frameOption: cloudfront.HeadersFrameOption.DENY,
          override: true,
        },
        referrerPolicy: {
          referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
          override: true,
        },
        strictTransportSecurity: {
          accessControlMaxAge: cdk.Duration.days(365),
          includeSubdomains: true,
          preload: false,    // don't lock us into the HSTS preload list yet
          override: true,
        },
        // X-XSS-Protection deliberately omitted: deprecated by all
        // major browsers, can introduce vulnerabilities. CSP
        // script-src is what actually defends here.
      },
    });
  }
}
