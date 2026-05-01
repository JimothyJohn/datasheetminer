/**
 * Cognito user pool for Specodex auth (Phase 1 of todo/AUTH.md).
 *
 * Deliberately self-contained:
 *   - Lives in its own subdirectory so this branch can land without
 *     touching api-stack / frontend-stack / bin/app.ts.
 *   - Not yet wired into the CDK app — Phase 2 imports `AuthStack`
 *     from `bin/app.ts` and grants the API Lambda access to the
 *     pool's IDs via SSM.
 *
 * What it provisions:
 *   - UserPool with email-as-username, self-signup, email
 *     verification, 12-char password policy.
 *   - UserPoolClient (public SPA client, no secret) configured for
 *     USER_PASSWORD_AUTH so the backend can proxy login from
 *     `POST /api/auth/login`.
 *   - "admin" group — replaces the binary `APP_MODE=admin` env gate
 *     once Phase 4 lands.
 *   - SSM parameters under `${ssmPrefix}/cognito/*` so the API
 *     Lambda's existing `loadSsmSecrets()` path can read them
 *     without a code change to `config/index.ts` (the SSM fetch
 *     already iterates over the prefix).
 *   - CfnOutputs mirroring the existing stack convention.
 */

import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { AppConfig } from '../config';

export class AuthStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;

  constructor(scope: Construct, id: string, config: AppConfig, props?: cdk.StackProps) {
    super(scope, id, props);

    this.userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `specodex-${config.stage}`,
      signInAliases: { email: true, username: false },
      autoVerify: { email: true },
      selfSignUpEnabled: true,
      standardAttributes: {
        email: { required: true, mutable: false },
      },
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      // Phase 5 swaps in a verified SES identity. Default Cognito
      // sender is fine for dev/staging; insufficient for prod sign-up
      // volume.
      email: cognito.UserPoolEmail.withCognito(),
      removalPolicy: config.stage === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
    });

    new cognito.CfnUserPoolGroup(this, 'AdminGroup', {
      userPoolId: this.userPool.userPoolId,
      groupName: 'admin',
      description: 'Users with admin privileges (replaces APP_MODE=admin gate).',
      precedence: 1,
    });

    this.userPoolClient = new cognito.UserPoolClient(this, 'WebClient', {
      userPool: this.userPool,
      userPoolClientName: `specodex-web-${config.stage}`,
      generateSecret: false,
      authFlows: {
        userPassword: true,
        userSrp: true,
      },
      preventUserExistenceErrors: true,
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      enableTokenRevocation: true,
    });

    new ssm.StringParameter(this, 'UserPoolIdParam', {
      parameterName: `${config.ssmPrefix}/cognito/user-pool-id`,
      stringValue: this.userPool.userPoolId,
      description: 'Cognito user pool ID for the Specodex API Lambda.',
    });

    new ssm.StringParameter(this, 'UserPoolClientIdParam', {
      parameterName: `${config.ssmPrefix}/cognito/user-pool-client-id`,
      stringValue: this.userPoolClient.userPoolClientId,
      description: 'Cognito web client ID for the Specodex SPA.',
    });

    new cdk.CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId });
    new cdk.CfnOutput(this, 'UserPoolClientId', { value: this.userPoolClient.userPoolClientId });
  }
}
