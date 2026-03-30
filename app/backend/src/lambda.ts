/**
 * AWS Lambda handler wrapping the Express application
 * Uses serverless-http to translate API Gateway events to Express requests
 *
 * Loads secrets from SSM Parameter Store on cold start.
 */

import serverlessHttp from 'serverless-http';
import app from './index';
import { loadSsmSecrets } from './config';

const ssmReady = loadSsmSecrets();
const serverless = serverlessHttp(app);

export const handler: typeof serverless = async (event, context) => {
  await ssmReady;
  return serverless(event, context);
};
