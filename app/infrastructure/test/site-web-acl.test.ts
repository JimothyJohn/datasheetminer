/**
 * SiteWebAcl synth assertions.
 *
 * Wraps the Construct in a throwaway Stack so we can run
 * Template.fromStack against it without standing up the full
 * frontend-stack.
 */

import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { SiteWebAcl } from '../lib/waf/site-web-acl';

function templateFor(props: ConstructorParameters<typeof SiteWebAcl>[2]): Template {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, 'TestWafHost', {
    env: { account: '111111111111', region: 'us-east-1' },
  });
  new SiteWebAcl(stack, 'TestAcl', props);
  return Template.fromStack(stack);
}

describe('SiteWebAcl', () => {
  it('creates a CLOUDFRONT-scoped web ACL with default-allow', () => {
    const t = templateFor({ stage: 'staging' });
    t.hasResourceProperties('AWS::WAFv2::WebACL', {
      Scope: 'CLOUDFRONT',
      DefaultAction: { Allow: {} },
      Name: 'specodex-staging-edge-acl',
    });
  });

  it('rate-limits anonymous reads at the configured limit', () => {
    const t = templateFor({ stage: 'staging', readRateLimit: 600 });
    t.hasResourceProperties('AWS::WAFv2::WebACL', {
      Rules: Match.arrayWith([
        Match.objectLike({
          Name: 'AnonymousReadRateLimit',
          Priority: 10,
          Action: { Block: {} },
          Statement: {
            RateBasedStatement: Match.objectLike({
              Limit: 600,
              AggregateKeyType: 'IP',
            }),
          },
        }),
      ]),
    });
  });

  it('rate-limits auth flow at the configured limit', () => {
    const t = templateFor({ stage: 'prod', authRateLimit: 60 });
    t.hasResourceProperties('AWS::WAFv2::WebACL', {
      Rules: Match.arrayWith([
        Match.objectLike({
          Name: 'AuthFlowRateLimit',
          Priority: 20,
          Statement: {
            RateBasedStatement: Match.objectLike({ Limit: 60 }),
          },
        }),
      ]),
    });
  });

  it('attaches AWS managed common rules', () => {
    const t = templateFor({ stage: 'staging' });
    t.hasResourceProperties('AWS::WAFv2::WebACL', {
      Rules: Match.arrayWith([
        Match.objectLike({
          Name: 'AWSManagedRulesCommonRuleSet',
          Priority: 30,
          OverrideAction: { None: {} },
          Statement: {
            ManagedRuleGroupStatement: {
              VendorName: 'AWS',
              Name: 'AWSManagedRulesCommonRuleSet',
            },
          },
        }),
      ]),
    });
  });

  it('omits Bot Control by default', () => {
    const t = templateFor({ stage: 'staging' });
    const acl = Object.values(t.toJSON().Resources).find(
      (r: any) => r.Type === 'AWS::WAFv2::WebACL',
    ) as any;
    const ruleNames = acl.Properties.Rules.map((r: any) => r.Name);
    expect(ruleNames).not.toContain('AWSManagedRulesBotControlRuleSet');
  });

  it('includes Bot Control when enabled', () => {
    const t = templateFor({ stage: 'staging', botControlEnabled: true });
    t.hasResourceProperties('AWS::WAFv2::WebACL', {
      Rules: Match.arrayWith([
        Match.objectLike({
          Name: 'AWSManagedRulesBotControlRuleSet',
          Priority: 40,
          Statement: {
            ManagedRuleGroupStatement: Match.objectLike({
              Name: 'AWSManagedRulesBotControlRuleSet',
            }),
          },
        }),
      ]),
    });
  });

  it('scopes the read-rate rule to /api/products and /api/v1/search', () => {
    const t = templateFor({ stage: 'staging' });
    const acl = Object.values(t.toJSON().Resources).find(
      (r: any) => r.Type === 'AWS::WAFv2::WebACL',
    ) as any;
    const readRule = acl.Properties.Rules.find((r: any) => r.Name === 'AnonymousReadRateLimit');
    const scopeDown = readRule.Statement.RateBasedStatement.ScopeDownStatement;
    const searchStrings = scopeDown.OrStatement.Statements.map(
      (s: any) => s.ByteMatchStatement.SearchString,
    );
    expect(searchStrings).toEqual(
      expect.arrayContaining(['/api/products', '/api/v1/search']),
    );
  });

  it('scopes the auth-rate rule to /api/auth/login and /api/auth/register', () => {
    const t = templateFor({ stage: 'staging' });
    const acl = Object.values(t.toJSON().Resources).find(
      (r: any) => r.Type === 'AWS::WAFv2::WebACL',
    ) as any;
    const authRule = acl.Properties.Rules.find((r: any) => r.Name === 'AuthFlowRateLimit');
    const scopeDown = authRule.Statement.RateBasedStatement.ScopeDownStatement;
    const searchStrings = scopeDown.OrStatement.Statements.map(
      (s: any) => s.ByteMatchStatement.SearchString,
    );
    expect(searchStrings).toEqual(
      expect.arrayContaining(['/api/auth/login', '/api/auth/register']),
    );
  });
});
