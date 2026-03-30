/**
 * CDK deployment configuration
 * Reads from environment variables (set by CI or local shell)
 */

export interface AppConfig {
  stage: string;
  env: { account: string; region: string };
  tableName: string;
  domainName?: string;
  certificateArn?: string;
  hostedZoneId?: string;
  ssmPrefix: string;
}

export function getConfig(): AppConfig {
  const stage = process.env.STAGE || 'dev';
  const account = process.env.AWS_ACCOUNT_ID || process.env.CDK_DEFAULT_ACCOUNT || '';
  const region = process.env.AWS_REGION || process.env.CDK_DEFAULT_REGION || 'us-east-1';

  if (!account) {
    throw new Error('AWS_ACCOUNT_ID or CDK_DEFAULT_ACCOUNT must be set');
  }

  return {
    stage,
    env: { account, region },
    tableName: process.env.DYNAMODB_TABLE_NAME || `products-${stage}`,
    domainName: process.env.DOMAIN_NAME,
    certificateArn: process.env.CERTIFICATE_ARN,
    hostedZoneId: process.env.HOSTED_ZONE_ID,
    ssmPrefix: `/datasheetminer/${stage}`,
  };
}
