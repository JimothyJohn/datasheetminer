import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigwIntegrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { AppConfig } from './config';
import * as path from 'path';

interface ApiStackProps extends cdk.StackProps {
  table: dynamodb.ITable;
  uploadBucket: s3.IBucket;
}

export class ApiStack extends cdk.Stack {
  public readonly api: apigw.HttpApi;

  constructor(scope: Construct, id: string, config: AppConfig, props: ApiStackProps) {
    super(scope, id, props);

    const { table, uploadBucket } = props;

    // Reference SSM parameters (created outside CDK or by CI pipeline)
    const geminiKeyParam = ssm.StringParameter.fromSecureStringParameterAttributes(this, 'GeminiKey', {
      parameterName: `${config.ssmPrefix}/gemini-api-key`,
    });

    const stripeLambdaUrlParam = ssm.StringParameter.fromStringParameterName(this, 'StripeLambdaUrl',
      `${config.ssmPrefix}/stripe-lambda-url`,
    );

    // Lambda function (backend API)
    const handler = new lambda.Function(this, 'ApiHandler', {
      functionName: `datasheetminer-api-${config.stage}`,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../backend/dist'), {
        bundling: {
          image: lambda.Runtime.NODEJS_18_X.bundlingImage,
          command: ['bash', '-c', 'cp -au . /asset-output'],
          user: 'root',
        },
      }),
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        NODE_ENV: 'production',
        STAGE: config.stage,
        APP_MODE: 'public',
        DYNAMODB_TABLE_NAME: table.tableName,
        UPLOAD_BUCKET: uploadBucket.bucketName,
        AWS_ACCOUNT_ID: config.env.account,
        // SSM paths — the Lambda reads secrets at startup
        SSM_PREFIX: config.ssmPrefix,
      },
    });

    // Grant DynamoDB and S3 access
    table.grantReadWriteData(handler);
    uploadBucket.grantReadWrite(handler);

    // Grant SSM read access for secrets
    geminiKeyParam.grantRead(handler);
    handler.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter', 'ssm:GetParameters'],
      resources: [
        `arn:aws:ssm:${config.env.region}:${config.env.account}:parameter${config.ssmPrefix}/*`,
      ],
    }));

    // HTTP API
    this.api = new apigw.HttpApi(this, 'HttpApi', {
      apiName: `datasheetminer-${config.stage}`,
      corsPreflight: {
        allowOrigins: ['*'],
        allowMethods: [apigw.CorsHttpMethod.ANY],
        allowHeaders: ['*'],
      },
    });

    const integration = new apigwIntegrations.HttpLambdaIntegration('LambdaIntegration', handler);
    this.api.addRoutes({
      path: '/{proxy+}',
      methods: [apigw.HttpMethod.ANY],
      integration,
    });

    new cdk.CfnOutput(this, 'ApiUrl', { value: this.api.url || '' });
  }
}
