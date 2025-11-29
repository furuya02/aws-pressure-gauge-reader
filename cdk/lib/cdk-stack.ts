import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { DockerImageCode, DockerImageFunction } from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';

export class CdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ========================================
    // ECRリポジトリの作成
    // ========================================
    const ecrRepository = new ecr.Repository(this, 'GaugeDetectionRepo', {
      repositoryName: 'pressure-gauge-detection',
      removalPolicy: cdk.RemovalPolicy.DESTROY, // 開発環境用
      autoDeleteImages: true, // 開発環境用
    });

    // ========================================
    // Lambda関数の作成（コンテナイメージ）
    // ========================================
    const gaugeDetectionFunction = new DockerImageFunction(this, 'GaugeDetectionFunction', {
      functionName: 'pressure-gauge-detection',
      code: DockerImageCode.fromImageAsset(path.join(__dirname, '../lambda'), {
        // Dockerfileのパスを指定
        file: 'Dockerfile',
        // ビルド時のプラットフォームを指定
        platform: cdk.aws_ecr_assets.Platform.LINUX_AMD64,
      }),
      memorySize: 3008, // 3GB
      timeout: cdk.Duration.seconds(120), // 120秒
      environment: {
        MODEL_PATH: '/opt/ml/model/best.pt',
        CONF_THRESHOLD: '0.65',
        IOU_THRESHOLD: '0.5',
        BEDROCK_REGION: 'us-east-1',  // Bedrock呼び出しリージョンを明示的に指定
      },
      description: 'Pressure gauge needle detection using YOLO segmentation',
    });

    // ========================================
    // Lambda関数のIAMロールにBedrock呼び出し権限を追加
    // ========================================
    gaugeDetectionFunction.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        // Allow all Claude Sonnet 4.5 models in all regions (us-east-1 only will be used via BEDROCK_REGION env var)
        `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-*`,
        `arn:aws:bedrock:*::foundation-model/us.anthropic.claude-sonnet-4-5-*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/*anthropic.claude-sonnet-4-5-*`,
      ],
    }));

    // ========================================
    // スタック出力
    // ========================================
    new cdk.CfnOutput(this, 'ECRRepositoryUri', {
      value: ecrRepository.repositoryUri,
      description: 'ECR Repository URI',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: gaugeDetectionFunction.functionName,
      description: 'Lambda Function Name',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionArn', {
      value: gaugeDetectionFunction.functionArn,
      description: 'Lambda Function ARN',
    });
  }
}
