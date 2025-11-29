#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CdkStack } from '../lib/cdk-stack';

const app = new cdk.App();
new CdkStack(app, 'PressureGaugeDetectionStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1'  // Bedrock Claude Sonnet 4.5対応リージョン
  },
  description: 'Pressure Gauge Detection with Bedrock Agent and YOLO Lambda',
});