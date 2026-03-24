/**
 * AWS Lambda handler wrapping the Express application
 * Uses serverless-http to translate API Gateway events to Express requests
 */

import serverlessHttp from 'serverless-http';
import app from './index';

export const handler = serverlessHttp(app);
