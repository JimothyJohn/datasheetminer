/**
 * Configuration management for the backend
 *
 * Local dev: reads from .env file
 * Production (Lambda): reads secrets from AWS SSM Parameter Store
 */

import dotenv from 'dotenv';
import path from 'path';

// Load .env for local development only
if (process.env.NODE_ENV !== 'production') {
  dotenv.config({ path: path.resolve(__dirname, '../../../../.env') });
}

const stage = process.env.STAGE || 'dev';
const appMode = (process.env.APP_MODE || 'admin') as 'public' | 'admin';
const ssmPrefix = process.env.SSM_PREFIX || `/datasheetminer/${stage}`;

export const config = {
  stage,
  appMode,
  port: parseInt(process.env.PORT || '3001', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  aws: {
    region: process.env.AWS_REGION || 'us-east-1',
    accountId: process.env.AWS_ACCOUNT_ID,
  },
  dynamodb: {
    tableName: process.env.DYNAMODB_TABLE_NAME || `products-${stage}`,
  },
  s3: {
    uploadBucket: process.env.UPLOAD_BUCKET || `datasheetminer-uploads-${stage}`,
  },
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
    credentials: true,
  },
  gemini: {
    apiKey: process.env.GEMINI_API_KEY,
  },
  stripe: {
    lambdaUrl: process.env.STRIPE_LAMBDA_URL || '',
  },
  ssmPrefix,
};

/**
 * Load runtime config from SSM Parameter Store (production only).
 * Call once at Lambda cold start before handling requests.
 *
 * GEMINI_API_KEY is intentionally NOT fetched here — the deployed app
 * doesn't scrape datasheets, only reads already-extracted records from
 * DynamoDB. Scraping runs locally via `./Quickstart process`, which reads
 * the key from .env.
 */
export async function loadSsmSecrets(): Promise<void> {
  if (process.env.NODE_ENV !== 'production') return;

  const { SSMClient, GetParametersCommand } = await import('@aws-sdk/client-ssm');
  const ssm = new SSMClient({ region: config.aws.region });

  const paramNames = [`${ssmPrefix}/stripe-lambda-url`];

  try {
    const result = await ssm.send(new GetParametersCommand({
      Names: paramNames,
      WithDecryption: true,
    }));

    for (const param of result.Parameters || []) {
      const key = param.Name?.split('/').pop();
      if (key === 'stripe-lambda-url') {
        config.stripe.lambdaUrl = param.Value || '';
      }
    }

    if (result.InvalidParameters?.length) {
      console.warn('SSM parameters not found:', result.InvalidParameters);
    }
  } catch (err) {
    console.error('Failed to load SSM secrets:', err);
  }
}

export default config;
