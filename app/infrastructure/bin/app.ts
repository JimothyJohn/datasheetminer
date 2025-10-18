#!/usr/bin/env node
/**
 * CDK app entry point
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DatabaseStack } from '../lib/database-stack';
import { ApiStack } from '../lib/api-stack';
import { getConfig } from '../lib/config';

const app = new cdk.App();
const config = getConfig();

// Create DynamoDB stack
const databaseStack = new DatabaseStack(app, 'DatasheetMinerDatabaseStack', config, {
  env: config.env,
  description: 'DynamoDB table for DatasheetMiner application',
});

// Create API stack
const apiStack = new ApiStack(app, 'DatasheetMinerApiStack', config, {
  env: config.env,
  description: 'API Gateway and Lambda for DatasheetMiner application',
  table: databaseStack.table,
});

// API stack depends on database stack
apiStack.addDependency(databaseStack);

// Add tags to all resources
cdk.Tags.of(app).add('Project', 'DatasheetMiner');
cdk.Tags.of(app).add('ManagedBy', 'CDK');
