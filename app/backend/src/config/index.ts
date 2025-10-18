/**
 * Configuration management for the backend
 */

import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || '3001', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  aws: {
    region: process.env.AWS_REGION || 'us-east-1',
    accountId: process.env.AWS_ACCOUNT_ID,
  },
  dynamodb: {
    tableName: process.env.DYNAMODB_TABLE_NAME || 'products',
  },
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
    credentials: true,
  },
};

export default config;
