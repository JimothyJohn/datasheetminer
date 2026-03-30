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
 * Load secrets from SSM Parameter Store (production only).
 * Call once at Lambda cold start before handling requests.
 */
export async function loadSsmSecrets(): Promise<void> {
  if (process.env.NODE_ENV !== 'production') return;

  const { SSMClient, GetParametersCommand } = await import('@aws-sdk/client-ssm');
  const ssm = new SSMClient({ region: config.aws.region });

  const paramNames = [
    `${ssmPrefix}/gemini-api-key`,
    `${ssmPrefix}/stripe-lambda-url`,
  ];

  try {
    const result = await ssm.send(new GetParametersCommand({
      Names: paramNames,
      WithDecryption: true,
    }));

    for (const param of result.Parameters || []) {
      const key = param.Name?.split('/').pop();
      switch (key) {
        case 'gemini-api-key':
          config.gemini.apiKey = param.Value;
          break;
        case 'stripe-lambda-url':
          config.stripe.lambdaUrl = param.Value || '';
          break;
      }
    }

    if (result.InvalidParameters?.length) {
      console.warn('SSM parameters not found:', result.InvalidParameters);
    }
  } catch (err) {
    console.error('Failed to load SSM secrets:', err);
  }
}

// Debug log for API Key presence
if (!config.gemini.apiKey && process.env.NODE_ENV !== 'production') {
  console.warn("GEMINI_API_KEY is missing in backend config!");
}

export default config;
