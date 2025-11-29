# AWS CDKでのClaude Sonnet 4.5利用ガイド

## 目次

1. [概要](#概要)
2. [AWS CDKバージョンの制約](#aws-cdkバージョンの制約)
3. [Inference Profile IDの必要性](#inference-profile-idの必要性)
4. [CDKでの実装方法](#cdkでの実装方法)
5. [IAMポリシー設定](#iamポリシー設定)
6. [リージョン設定の重要性](#リージョン設定の重要性)
7. [よくある問題と解決策](#よくある問題と解決策)

## 概要

Claude Sonnet 4.5 (2025年9月リリース版) をAWS CDKで利用する際には、いくつかの制約と注意点があります。本ドキュメントでは、実際のプロジェクト経験に基づき、これらの制約を回避し、正しく実装する方法を解説します。

### 使用環境

- **AWS CDK**: 2.220.0
- **Claude Sonnet 4.5モデルID**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
- **リージョン**: us-east-1

## AWS CDKバージョンの制約

### CDK 2.220.0の制限

AWS CDK 2.220.0（2024年12月時点で安定版）では、Bedrock関連の一部機能がL2 Constructとして提供されていません。

#### 利用可能なConstruct

```typescript
import * as bedrock from 'aws-cdk-lib/aws-bedrock';

// ✅ L1 Construct - 利用可能
new bedrock.CfnAgent(this, 'Agent', { ... });
new bedrock.CfnAgentAlias(this, 'AgentAlias', { ... });
new bedrock.CfnDataSource(this, 'DataSource', { ... });
new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', { ... });
```

#### 利用不可能な機能

```typescript
// ❌ L2 Construct - まだ提供されていない
// new bedrock.Agent(this, 'Agent', { ... });

// ❌ Bedrock Agent Action Groupの詳細設定
// - Code Interpreter機能の有効化
// - パラメータスキーマの型安全な定義
```

### 回避策

L1 Construct（`CfnAgent`など）を使用するか、AWS CLIで直接設定します。

```typescript
// L1 Constructを使用
const cfnAgent = new bedrock.CfnAgent(this, 'Agent', {
  agentName: 'my-agent',
  foundationModel: 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
  // ...
});
```

または、CDK外でAWS CLIを使用：

```bash
aws bedrock-agent create-agent-action-group \
  --agent-id FG9EIWNA4O \
  --parent-action-group-signature AMAZON.CodeInterpreter
```

## Inference Profile IDの必要性

### Foundation Model IDとInference Profile IDの違い

Claude Sonnet 4.5は、**Inference Profile経由でのみ**呼び出し可能です。

#### Foundation Model ID（使用不可）

```python
# ❌ このIDでは呼び出しできない
model_id = "anthropic.claude-sonnet-4-5-20250929-v1:0"
```

**エラー:**
```
ValidationException: Invocation of model ID anthropic.claude-sonnet-4-5-20250929-v1:0
with on-demand throughput isn't supported. Retry your request with the ID or ARN
of an inference profile that contains this model.
```

#### Inference Profile ID（正しい）

```python
# ✅ このIDを使用
model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
```

### Inference Profileとは

Inference Profileは、複数のリージョンにまたがるモデルへのアクセスを提供するAWS Bedrockの機能です。

**特徴:**
- クロスリージョン推論をサポート
- トラフィックのロードバランシング
- 自動フェイルオーバー

**構造:**
```
Inference Profile: us.anthropic.claude-sonnet-4-5-20250929-v1:0
├─ Region: us-east-1
│  └─ Foundation Model: anthropic.claude-sonnet-4-5-20250929-v1:0
├─ Region: us-west-2
│  └─ Foundation Model: anthropic.claude-sonnet-4-5-20250929-v1:0
└─ Region: eu-west-1
   └─ Foundation Model: anthropic.claude-sonnet-4-5-20250929-v1:0
```

### プレフィックスの意味

| プレフィックス | 意味 | 用途 |
|-------------|------|------|
| `us.` | US リージョンのInference Profile | ✅ **本プロジェクトで使用** |
| `eu.` | EU リージョンのInference Profile | EU居住者データ用 |
| `ap.` | Asia-Pacific リージョンのInference Profile | APAC地域用 |
| (なし) | Foundation Model ID | ❌ 直接呼び出し不可 |

## CDKでの実装方法

### Lambda関数でのBedrock呼び出し

本プロジェクトでは、Bedrock Agentを使用せず、Lambda関数から直接Bedrock LLMを呼び出しています。

#### Lambda関数コード

```python
import boto3
import json
import os

# グローバル変数（コールドスタート対策）
bedrock_client = None

def initialize_bedrock_client():
    """Bedrock Runtimeクライアントを初期化"""
    global bedrock_client

    if bedrock_client is None:
        # 環境変数からリージョンを取得
        region = os.environ.get("BEDROCK_REGION", "us-east-1")
        print(f"Initializing Bedrock Runtime client in region: {region}")

        bedrock_client = boto3.client("bedrock-runtime", region_name=region)
        print("Bedrock Runtime client initialized successfully")

    return bedrock_client

def invoke_bedrock_model(
    client,
    processed_image_base64: str,
    user_text: str,
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # ✅ Inference Profile ID
) -> str:
    """Bedrock LLMを呼び出して画像を解析"""

    # Claude 3.5 Sonnet用のリクエストボディを構築
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": processed_image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": user_text
                    }
                ]
            }
        ]
    }

    print(f"Calling Bedrock model: {model_id}")

    # Bedrock APIを呼び出し
    response = client.invoke_model(
        modelId=model_id,  # ✅ Inference Profile ID
        body=json.dumps(request_body)
    )

    # レスポンスを解析
    response_body = json.loads(response["body"].read())
    llm_response = response_body["content"][0]["text"]

    return llm_response

def lambda_handler(event, context):
    # Bedrockクライアントを初期化
    bedrock = initialize_bedrock_client()

    # LLMを呼び出し
    llm_response = invoke_bedrock_model(
        client=bedrock,
        processed_image_base64=image_base64,
        user_text=user_text
    )

    return {"llmResponse": llm_response}
```

#### CDKスタック定義

```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';

export class MyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda関数の作成
    const myFunction = new lambda.DockerImageFunction(this, 'MyFunction', {
      code: lambda.DockerImageCode.fromImageAsset('./lambda'),
      memorySize: 3008,
      timeout: cdk.Duration.seconds(120),
      environment: {
        BEDROCK_REGION: 'us-east-1',  // ✅ リージョンを明示的に指定
      },
    });

    // ✅ IAMポリシーを追加
    myFunction.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
      ],
      resources: [
        // ✅ 全リージョン対応（内部ルーティングに対応）
        `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-*`,
        `arn:aws:bedrock:*::foundation-model/us.anthropic.claude-sonnet-4-5-*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/*anthropic.claude-sonnet-4-5-*`,
      ],
    }));
  }
}
```

## IAMポリシー設定

### 問題: リージョンの不一致

Inference Profileは内部的に最適なリージョンにルーティングするため、`region_name`で指定したリージョンと異なるリージョンにアクセスされる場合があります。

#### 現象

```python
# Lambda関数コード
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
```

```
# しかし実際のアクセスは...
AccessDeniedException: ... arn:aws:bedrock:us-east-2::foundation-model/...
```

**us-east-1**を指定したのに、**us-east-2**にアクセスされています。

### 解決策: ワイルドカードによる全リージョン許可

IAMポリシーで全リージョンを許可します。

```typescript
resources: [
  // ✅ リージョンをワイルドカード (*) で指定
  `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-*`,
  `arn:aws:bedrock:*::foundation-model/us.anthropic.claude-sonnet-4-5-*`,
  `arn:aws:bedrock:*:${this.account}:inference-profile/*anthropic.claude-sonnet-4-5-*`,
]
```

### セキュリティ上の懸念

「全リージョン許可は危険では？」という懸念に対して：

**安全性:**
- ✅ モデルIDでフィルタリング（Claude Sonnet 4.5のみ）
- ✅ Lambda関数コードで`BEDROCK_REGION`環境変数により制御
- ✅ Inference Profileが自動ルーティングするため、リージョン指定は推奨されない

**代替案:**
実際にアクセスされるリージョンを特定して許可する場合：

```typescript
resources: [
  // us-east-1とus-east-2のみ許可
  `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5-*`,
  `arn:aws:bedrock:us-east-2::foundation-model/anthropic.claude-sonnet-4-5-*`,
  `arn:aws:bedrock:us-east-1:${this.account}:inference-profile/*anthropic.claude-sonnet-4-5-*`,
  `arn:aws:bedrock:us-east-2:${this.account}:inference-profile/*anthropic.claude-sonnet-4-5-*`,
]
```

しかし、Inference Profileのルーティングロジックは将来変更される可能性があるため、**ワイルドカードを推奨**します。

## リージョン設定の重要性

### 環境変数による制御

Lambda関数では環境変数`BEDROCK_REGION`でリージョンを制御します。

```typescript
// CDKスタック
environment: {
  BEDROCK_REGION: 'us-east-1',  // ✅ us-east-1に統一
}
```

```python
# Lambda関数
region = os.environ.get("BEDROCK_REGION", "us-east-1")
bedrock_client = boto3.client("bedrock-runtime", region_name=region)
```

### AWS_REGION環境変数の制約

Lambda実行環境では`AWS_REGION`環境変数が予約されており、CDKで設定できません。

```typescript
// ❌ エラーになる
environment: {
  AWS_REGION: 'us-east-1',  // ValidationError: AWS_REGION is reserved
}
```

**解決策:** カスタム環境変数（`BEDROCK_REGION`）を使用

### Model Accessの有効化

Claude Sonnet 4.5を使用する前に、AWS Consoleでモデルアクセスを有効化する必要があります。

**手順:**

1. AWS Console → Amazon Bedrock
2. 左メニュー → **Model access**
3. リージョンを**us-east-1**に変更
4. **Manage model access**をクリック
5. **Anthropic** → **Claude Sonnet 4.5** (`anthropic.claude-sonnet-4-5-20250929-v1:0`) にチェック
6. **Request model access**をクリック

**承認時間:** 通常は即時、最大で数分

## よくある問題と解決策

### 問題1: ValidationException (on-demand throughput)

```
ValidationException: Invocation of model ID anthropic.claude-sonnet-4-5-20250929-v1:0
with on-demand throughput isn't supported.
```

**原因:** Foundation Model IDを使用している

**解決策:** Inference Profile IDに変更

```python
# ❌ 間違い
model_id = "anthropic.claude-sonnet-4-5-20250929-v1:0"

# ✅ 正しい
model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
```

### 問題2: AccessDeniedException (別リージョン)

```
AccessDeniedException: ... arn:aws:bedrock:us-east-2::foundation-model/...
```

**原因:** IAMポリシーが指定リージョンのみ許可している

**解決策:** ワイルドカードで全リージョンを許可

```typescript
resources: [
  `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-*`,
  // ...
]
```

### 問題3: Model Accessエラー

```
AccessDeniedException: You don't have access to the model with the specified model ID.
```

**原因:** Bedrock Model Accessが有効化されていない

**解決策:**
1. AWS Console → Amazon Bedrock → Model access
2. リージョンを**us-east-1**に設定
3. Claude Sonnet 4.5を有効化

### 問題4: CDKでCode Interpreterを設定できない

```typescript
// ❌ TypeScriptエラー
const agent = new bedrock.CfnAgent(this, 'Agent', {
  enableCodeInterpreter: true,  // Property does not exist
});
```

**原因:** CDK 2.220.0はCode Interpreter機能をサポートしていない

**解決策:** AWS CLIで設定

```bash
aws bedrock-agent create-agent-action-group \
  --agent-id <AGENT_ID> \
  --agent-version DRAFT \
  --action-group-name CodeInterpreterAction \
  --parent-action-group-signature AMAZON.CodeInterpreter
```

### 問題5: リージョン間のModel Accessの違い

us-east-1でModel Accessを有効化しても、他のリージョンでは有効化されていない場合があります。

**確認方法:**

```bash
# us-east-1のModel Access確認
aws bedrock list-foundation-models --region us-east-1 \
  --by-provider anthropic

# us-west-2のModel Access確認
aws bedrock list-foundation-models --region us-west-2 \
  --by-provider anthropic
```

**解決策:** 使用する全リージョンでModel Accessを有効化

## まとめ

### チェックリスト

- ✅ Inference Profile ID（`us.anthropic.claude-sonnet-4-5-20250929-v1:0`）を使用
- ✅ IAMポリシーで全リージョンを許可（`arn:aws:bedrock:*::...`）
- ✅ Lambda環境変数で`BEDROCK_REGION=us-east-1`を設定
- ✅ AWS ConsoleでModel Accessを有効化（us-east-1）
- ✅ CDK L1 Construct（`CfnAgent`など）を使用
- ✅ Code Interpreter機能はAWS CLIで設定

### 推奨設定

```typescript
// CDKスタック
const lambdaFunction = new lambda.DockerImageFunction(this, 'Function', {
  environment: {
    BEDROCK_REGION: 'us-east-1',  // ✅ リージョン明示
  },
});

lambdaFunction.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
  resources: [
    // ✅ 全リージョン許可
    `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-*`,
    `arn:aws:bedrock:*::foundation-model/us.anthropic.claude-sonnet-4-5-*`,
    `arn:aws:bedrock:*:${this.account}:inference-profile/*anthropic.claude-sonnet-4-5-*`,
  ],
}));
```

```python
# Lambda関数
def initialize_bedrock_client():
    region = os.environ.get("BEDROCK_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)

def invoke_bedrock_model(client, image_base64, text):
    model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # ✅ Inference Profile ID
    # ...
```

これらの設定により、AWS CDK環境でClaude Sonnet 4.5を安定して利用できます。
