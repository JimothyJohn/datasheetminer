import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { AppConfig } from './config';

export interface DatabaseStackProps extends cdk.StackProps {
  table?: dynamodb.ITable;
  uploadBucket?: s3.IBucket;
}

export class DatabaseStack extends cdk.Stack {
  public readonly table: dynamodb.Table;
  public readonly uploadBucket: s3.Bucket;

  constructor(scope: Construct, id: string, config: AppConfig, props?: cdk.StackProps) {
    super(scope, id, props);

    this.table = new dynamodb.Table(this, 'ProductsTable', {
      tableName: config.tableName,
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: config.stage === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
    });

    this.uploadBucket = new s3.Bucket(this, 'UploadBucket', {
      bucketName: `datasheetminer-uploads-${config.stage}-${config.env.account}`,
      removalPolicy: config.stage === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: config.stage !== 'prod',
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        { prefix: 'done/', expiration: cdk.Duration.days(90) },
      ],
      cors: [
        {
          allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.POST],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
    });

    new cdk.CfnOutput(this, 'TableName', { value: this.table.tableName });
    new cdk.CfnOutput(this, 'UploadBucketName', { value: this.uploadBucket.bucketName });
  }
}
