#!/usr/bin/env node
/**
 * CDK app entry point
 * Deploys: DynamoDB -> API Gateway + Lambda -> S3 + CloudFront
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DatabaseStack } from '../lib/database-stack';
import { ApiStack } from '../lib/api-stack';
import { FrontendStack } from '../lib/frontend-stack';
import { getConfig } from '../lib/config';

const app = new cdk.App();
const config = getConfig();
const stage = config.stage; // dev | staging | prod
const prefix = `DatasheetMiner-${stage.charAt(0).toUpperCase() + stage.slice(1)}`;

// DynamoDB table
const databaseStack = new DatabaseStack(app, `${prefix}-Database`, config, {
  env: config.env,
  description: `DynamoDB table for DatasheetMiner (${stage})`,
});

// API Gateway + Lambda
const apiStack = new ApiStack(app, `${prefix}-Api`, config, {
  env: config.env,
  description: `API Gateway and Lambda for DatasheetMiner (${stage})`,
  table: databaseStack.table,
  uploadBucket: databaseStack.uploadBucket,
});
apiStack.addDependency(databaseStack);

// S3 + CloudFront (frontend)
const frontendStack = new FrontendStack(app, `${prefix}-Frontend`, config, {
  env: config.env,
  description: `S3 and CloudFront for DatasheetMiner frontend (${stage})`,
  api: apiStack.api,
});
frontendStack.addDependency(apiStack);

// Tag all resources
cdk.Tags.of(app).add('Project', 'DatasheetMiner');
cdk.Tags.of(app).add('Stage', stage);
cdk.Tags.of(app).add('ManagedBy', 'CDK');
