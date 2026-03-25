/**
 * Configuration management for the backend
 */

import dotenv from 'dotenv';

import path from 'path';

// Load environment variables from root (3 levels up from src/config/index.ts)
// app/backend/src/config/index.ts -> app/backend/src/config -> app/backend/src -> app/backend -> app -> root
dotenv.config({ path: path.resolve(__dirname, '../../../../.env') });

const stage = process.env.STAGE || 'dev';
const appMode = (process.env.APP_MODE || 'admin') as 'public' | 'admin';

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
};

// Debug log for API Key presence
if (!config.gemini.apiKey) {
  console.warn("⚠️  GEMINI_API_KEY is missing in backend config!");
} else {
  console.log("✅ GEMINI_API_KEY is set (starts with " + config.gemini.apiKey.substring(0, 4) + "...)");
}

export default config;
