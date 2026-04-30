/**
 * S3 + CloudFront stack for serving the frontend
 * Routes /api/* to API Gateway, everything else to S3
 */

import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as apigwv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import { Construct } from 'constructs';
import { AppConfig } from './config';
import * as path from 'path';

export interface FrontendStackProps extends cdk.StackProps {
  api: apigwv2.HttpApi;
}

export class FrontendStack extends cdk.Stack {
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, config: AppConfig, props: FrontendStackProps) {
    super(scope, id, props);

    // S3 bucket for frontend static files
    const bucket = new s3.Bucket(this, 'FrontendBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // API Gateway (HTTP API v2) origin for /api/* requests.
    // The $default auto-deploy stage has no URL path prefix, so there's no
    // originPath — unlike RestApi v1, which needed /prod.
    const apiOrigin = new origins.HttpOrigin(
      `${props.api.apiId}.execute-api.${this.region}.amazonaws.com`,
      {
        protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
      }
    );

    // S3 origin for frontend assets
    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(bucket);

    // Resolve ACM certificate for CloudFront (must be in us-east-1)
    const certificate = config.domain
      ? acm.Certificate.fromCertificateArn(this, 'SiteCertificate', config.domain.certificateArn)
      : undefined;

    // CloudFront distribution
    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: s3Origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: apiOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        },
        '/health': {
          origin: apiOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        },
      },
      defaultRootObject: 'index.html',
      // Custom domain + TLS
      ...(config.domain ? {
        domainNames: [config.domain.domainName],
        certificate,
      } : {}),
      // SPA: return index.html for client-side routes
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.minutes(5),
        },
      ],
    });

    // Route53 A record: datasheets.advin.io → CloudFront
    //
    // fromLookup resolves the zone by name at synth time and caches the
    // result in cdk.context.json (committed to the repo). No HOSTED_ZONE_ID
    // secret to keep in sync, no class of "wrong-zone" bug. Requires the
    // deploy role to have route53:ListHostedZonesByName + route53:GetHostedZone.
    if (config.domain) {
      const hostedZone = route53.HostedZone.fromLookup(this, 'HostedZone', {
        domainName: config.domain.hostedZoneName,
      });

      new route53.ARecord(this, 'SiteAliasRecord', {
        zone: hostedZone,
        recordName: config.domain.domainName,
        target: route53.RecordTarget.fromAlias(
          new targets.CloudFrontTarget(this.distribution),
        ),
      });
    }

    // Deploy all frontend files to S3 with short default cache.
    // Vite-hashed assets (JS/CSS) are cache-busted by filename so the
    // short TTL only matters for index.html — the file that must update
    // immediately on deploy.  This avoids the split-deployment pitfall
    // where exclude patterns can silently drop index.html.
    new s3deploy.BucketDeployment(this, 'DeployFrontend', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '../../frontend/dist'))],
      destinationBucket: bucket,
      distribution: this.distribution,
      distributionPaths: ['/*'],
      cacheControl: [s3deploy.CacheControl.maxAge(cdk.Duration.seconds(60)), s3deploy.CacheControl.mustRevalidate()],
    });

    // Outputs
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: `CloudFront distribution URL (${config.stage})`,
      exportName: `Specodex-${config.stage}-FrontendUrl`,
    });

    if (config.domain) {
      new cdk.CfnOutput(this, 'SiteUrl', {
        value: `https://${config.domain.domainName}`,
        description: `Custom domain URL (${config.stage})`,
        exportName: `Specodex-${config.stage}-SiteUrl`,
      });
    }

    new cdk.CfnOutput(this, 'DistributionId', {
      value: this.distribution.distributionId,
      description: `CloudFront distribution ID (${config.stage})`,
      exportName: `Specodex-${config.stage}-DistributionId`,
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: bucket.bucketName,
      description: `Frontend S3 bucket name (${config.stage})`,
      exportName: `Specodex-${config.stage}-FrontendBucket`,
    });
  }
}
