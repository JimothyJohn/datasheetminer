/**
 * CDK deployment configuration
 * Reads from environment variables (set by CI or local shell)
 */

export interface DomainConfig {
  domainName: string;
  certificateArn: string;
  hostedZoneName: string;
}

export interface AppConfig {
  stage: string;
  env: { account: string; region: string };
  tableName: string;
  domain?: DomainConfig;
  ssmPrefix: string;
}

export function getConfig(): AppConfig {
  const stage = process.env.STAGE || 'dev';
  const account = process.env.AWS_ACCOUNT_ID || process.env.CDK_DEFAULT_ACCOUNT || '';
  const region = process.env.AWS_REGION || process.env.CDK_DEFAULT_REGION || 'us-east-1';

  if (!account) {
    throw new Error('AWS_ACCOUNT_ID or CDK_DEFAULT_ACCOUNT must be set');
  }

  const domainName = process.env.DOMAIN_NAME;
  const certificateArn = process.env.CERTIFICATE_ARN;
  let domain: DomainConfig | undefined;
  if (domainName && certificateArn) {
    // HOSTED_ZONE_NAME is optional — default to the parent of DOMAIN_NAME
    // (e.g. datasheets.advin.io → advin.io). `||` (not `??`) so that an
    // empty string from an unset GitHub Actions secret falls back too —
    // empty here renders the record name as `datasheets.advin.io..` and
    // Route53 rejects it with DomainLabelEmpty.
    const hostedZoneName =
      process.env.HOSTED_ZONE_NAME || domainName.split('.').slice(1).join('.');
    domain = { domainName, certificateArn, hostedZoneName };
  }

  return {
    stage,
    env: { account, region },
    tableName: process.env.DYNAMODB_TABLE_NAME || `products-${stage}`,
    domain,
    ssmPrefix: `/datasheetminer/${stage}`,
  };
}
