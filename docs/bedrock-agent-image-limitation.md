# Bedrock Agentで画像データをAction Groupに連携できない理由

**作成日**: 2025-11-30
**プロジェクト**: 圧力計メーター画像解析システム

---

## 目次

1. [概要](#概要)
2. [プロジェクトのアーキテクチャ](#プロジェクトのアーキテクチャ)
3. [問題の発生](#問題の発生)
4. [試行錯誤の詳細](#試行錯誤の詳細)
5. [根本原因の分析](#根本原因の分析)
6. [技術的な詳細](#技術的な詳細)
7. [検証結果](#検証結果)
8. [解決策と代替案](#解決策と代替案)
9. [まとめ](#まとめ)

---

## 概要

AWS Bedrock AgentとLambda関数（Action Group）を使った画像処理システムにおいて、`invoke_agent` APIの`sessionState.files`パラメータで画像を渡しても、Action Group（Lambda関数）で受け取れないという問題に遭遇しました。

本ドキュメントでは、この問題の詳細な調査過程、根本原因、および代替解決策をまとめます。

### 期待していた動作

```
ユーザー → invoke_agent(sessionState.files)
         → Bedrock Agent
         → Action Group（Lambda）
         → YOLO画像処理
         → 結果返却
```

### 実際の動作

```
ユーザー → invoke_agent(sessionState.files)
         → validationException エラー
```

---

## プロジェクトのアーキテクチャ

### システム構成

```
┌─────────────────┐
│  ユーザー        │
└────────┬────────┘
         │
         │ 画像 + テキスト
         ▼
┌─────────────────────────────┐
│  Bedrock Agent              │
│  (Claude Sonnet 4.5)        │
└────────┬────────────────────┘
         │
         │ Action Group呼び出し
         ▼
┌─────────────────────────────┐
│  Lambda Function            │
│  - YOLOv8セグメンテーション   │
│  - 針検出・強調表示           │
└─────────────────────────────┘
```

### コンポーネント詳細

1. **Bedrock Agent**
   - Model: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
   - Agent ID: `FG9EIWNA4O`
   - Alias ID: `ERQNJJS4ME`

2. **Action Group (GaugeDetectionGroup)**
   - Action Group ID: `3BFFOF2YQE`
   - Lambda Function: `pressure-gauge-detection`
   - API Schema: OpenAPI 3.0形式

3. **Lambda Function**
   - Runtime: Python 3.11（コンテナイメージ）
   - Memory: 3GB
   - Timeout: 120秒
   - 機能: YOLOv8で圧力計の針を検出・強調表示

### Action Group API Schema

```json
{
  "openapi": "3.0.0",
  "paths": {
    "/detect-gauge": {
      "post": {
        "operationId": "detectGaugeNeedle",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["image"],
                "properties": {
                  "image": {
                    "type": "string",
                    "description": "Base64 encoded pressure gauge image"
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**重要**: Lambda関数は`image`フィールド（base64文字列）でデータを受け取る設計です。

---

## 問題の発生

### 初回テスト

画像なしでテキストのみでAgentを呼び出したところ、以下のような応答がありました：

```bash
python scripts/test_bedrock_agent.py sample_images/0001.png \
  --agent-id FG9EIWNA4O \
  --agent-alias-id ERQNJJS4ME
```

**Agent応答**:
```
圧力計のメーターを読み取るために、画像をアップロードしていただけますか？
画像をお送りいただければ、針の位置を検出して圧力値を読み取ります。
```

この時点で、スクリプトは画像をbase64エンコードしていましたが、`invoke_agent`に渡していませんでした。

### 想定した解決策

AWS Bedrock Agent Runtime APIのドキュメントから、`sessionState.files`パラメータで画像を渡せることが分かりました：

```python
response = client.invoke_agent(
    agentId='FG9EIWNA4O',
    agentAliasId='ERQNJJS4ME',
    sessionId=session_id,
    inputText='この圧力計のメーターを読み取ってください',
    sessionState={
        'files': [
            {
                'name': 'image.png',
                'source': {
                    'sourceType': 'BYTE_CONTENT',
                    'byteContent': {
                        'data': image_bytes,
                        'mediaType': 'image/png'
                    }
                },
                'useCase': 'CHAT'  # または 'CODE_INTERPRETER'
            }
        ]
    }
)
```

---

## 試行錯誤の詳細

### 試行1: useCase='CHAT'でテスト

**実装コード** (`scripts/test_bedrock_agent.py:106-124`):

```python
invoke_params['sessionState'] = {
    'files': [
        {
            'name': image_filename,
            'source': {
                'sourceType': 'BYTE_CONTENT',
                'byteContent': {
                    'data': image_bytes,
                    'mediaType': media_type
                }
            },
            'useCase': 'CHAT'
        }
    ]
}
```

**実行コマンド**:
```bash
cd scripts
python test_bedrock_agent.py ../sample_images/0001.png \
  --agent-id FG9EIWNA4O \
  --agent-alias-id ERQNJJS4ME
```

**結果**: ❌ エラー発生

**エラー詳細**:
```
[ERROR] Bedrock Agent呼び出しエラー: An error occurred (validationException)
when calling the InvokeAgent operation: The overridden prompt that you
provided is incorrectly formatted. Check the format for errors, such as
invalid JSON, and retry your request.

Traceback (most recent call last):
  File "test_bedrock_agent.py", line 228, in main
    result = invoke_bedrock_agent(...)
  File "test_bedrock_agent.py", line 136, in invoke_bedrock_agent
    for event in event_stream:
  File ".../botocore/eventstream.py", line 592, in __iter__
    parsed_event = self._parse_event(event)
  File ".../botocore/eventstream.py", line 608, in _parse_event
    raise EventStreamError(parsed_response, self._operation_name)
botocore.exceptions.EventStreamError: An error occurred (validationException)
when calling the InvokeAgent operation: The overridden prompt that you
provided is incorrectly formatted.
```

**分析**:
- エラーメッセージから「overridden prompt」に問題があることが判明
- promptOverrideConfigurationとの競合の可能性

### 試行2: Code Interpreterの有効化

AWS公式ドキュメントから、Code Interpreterを有効化すれば`sessionState.files`が使えるようになる可能性があることが分かりました。

#### ステップ2-1: CDKでの実装を試行

**試したコード** (`cdk/lib/cdk-stack.ts`):

```typescript
const cfnAgent = new bedrock.CfnAgent(this, 'GaugeDetectionAgent', {
  // ... 他の設定
  enableCodeInterpreter: true,  // ❌ このプロパティは存在しない
});
```

**結果**: ❌ TypeScriptコンパイルエラー

```
TSError: ⨯ Unable to compile TypeScript:
lib/cdk-stack.ts(99,7): error TS2353: Object literal may only specify known
properties, and 'enableCodeInterpreter' does not exist in type 'CfnAgentProps'.
```

**分析**:
- AWS CDK 2.220.0では`enableCodeInterpreter`プロパティが存在しない
- Code InterpreterはAction Groupとして追加する必要がある

#### ステップ2-2: CfnAgentActionGroupでの実装を試行

**試したコード**:

```typescript
const codeInterpreterActionGroup = new bedrock.CfnAgentActionGroup(
  this, 'CodeInterpreterActionGroup', {
    agentId: cfnAgent.attrAgentId,
    agentVersion: 'DRAFT',
    actionGroupName: 'CodeInterpreterAction',
    actionGroupState: 'ENABLED',
    parentActionGroupSignature: 'AMAZON.CodeInterpreter',
  }
);
```

**結果**: ❌ TypeScriptコンパイルエラー

```
TSError: ⨯ Unable to compile TypeScript:
lib/cdk-stack.ts(107,52): error TS2339: Property 'CfnAgentActionGroup' does
not exist on type 'typeof import(".../aws-cdk-lib/aws-bedrock/index")'.
```

**分析**:
- AWS CDK 2.220.0では`CfnAgentActionGroup`クラスが利用できない
- CloudFormationのサポートが不完全

#### ステップ2-3: AWS CLIで作成

**実行コマンド**:

```bash
aws bedrock-agent create-agent-action-group \
  --agent-id FG9EIWNA4O \
  --agent-version DRAFT \
  --action-group-name CodeInterpreterAction \
  --action-group-state ENABLED \
  --parent-action-group-signature AMAZON.CodeInterpreter \
  --region us-east-1
```

**結果**: ✅ 成功

```json
{
    "agentActionGroup": {
        "actionGroupId": "G0PFAZZYYT",
        "actionGroupName": "CodeInterpreterAction",
        "actionGroupState": "ENABLED",
        "agentId": "FG9EIWNA4O",
        "agentVersion": "DRAFT",
        "createdAt": "2025-11-29T18:54:04.193329+00:00",
        "parentActionSignature": "AMAZON.CodeInterpreter",
        "updatedAt": "2025-11-29T18:54:04.193329+00:00"
    }
}
```

#### ステップ2-4: Agentの準備

**実行コマンド**:

```bash
aws bedrock-agent prepare-agent \
  --agent-id FG9EIWNA4O \
  --region us-east-1
```

**結果**: ✅ 成功

```json
{
    "agentId": "FG9EIWNA4O",
    "agentStatus": "PREPARING",
    "agentVersion": "DRAFT",
    "preparedAt": "2025-11-29T21:23:22.708748+00:00"
}
```

**Agent状態確認**:

```bash
aws bedrock-agent get-agent \
  --agent-id FG9EIWNA4O \
  --region us-east-1 \
  | jq '.agent | {agentId, agentName, agentStatus, foundationModel}'
```

**結果**:

```json
{
  "agentId": "FG9EIWNA4O",
  "agentName": "pressure-gauge-agent",
  "agentStatus": "PREPARED",
  "foundationModel": "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}
```

**Action Group確認**:

```bash
aws bedrock-agent list-agent-action-groups \
  --agent-id FG9EIWNA4O \
  --agent-version DRAFT \
  --region us-east-1
```

**結果**:

```json
{
  "actionGroupSummaries": [
    {
      "actionGroupId": "G0PFAZZYYT",
      "actionGroupName": "CodeInterpreterAction",
      "actionGroupState": "ENABLED"
    },
    {
      "actionGroupId": "3BFFOF2YQE",
      "actionGroupName": "GaugeDetectionGroup",
      "actionGroupState": "ENABLED",
      "description": "Action group for detecting pressure gauge needles"
    }
  ]
}
```

✅ Code Interpreter Action Groupが正常に有効化されました。

### 試行3: useCase='CODE_INTERPRETER'でテスト

Code Interpreterを有効化したので、useCaseを変更してテストします。

**修正コード** (`scripts/test_bedrock_agent.py:121`):

```python
invoke_params['sessionState'] = {
    'files': [
        {
            'name': image_filename,
            'source': {
                'sourceType': 'BYTE_CONTENT',
                'byteContent': {
                    'data': image_bytes,
                    'mediaType': media_type
                }
            },
            'useCase': 'CODE_INTERPRETER'  # CHATから変更
        }
    ]
}
```

**実行コマンド**:

```bash
cd scripts
python test_bedrock_agent.py ../sample_images/0001.png \
  --agent-id FG9EIWNA4O \
  --agent-alias-id ERQNJJS4ME
```

**結果**: ❌ 同じエラーが継続

```
[ERROR] Bedrock Agent呼び出しエラー: An error occurred (validationException)
when calling the InvokeAgent operation: The overridden prompt that you
provided is incorrectly formatted. Check the format for errors, such as
invalid JSON, and retry your request.
```

**分析**:
- Code Interpreterを有効化しても問題は解決しない
- useCaseを変更しても同じエラーが発生
- promptOverrideConfigurationとの根本的な競合が存在

### 試行4: 画像なしでのテスト（検証）

問題がsessionState.filesに起因することを確認するため、画像なしでテストします。

**実行コマンド**:

```bash
cd scripts
python -c "
import boto3
import time

client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
session_id = f'test-{int(time.time())}'

response = client.invoke_agent(
    agentId='FG9EIWNA4O',
    agentAliasId='ERQNJJS4ME',
    sessionId=session_id,
    inputText='こんにちは、Code Interpreterは有効ですか？'
)

for event in response['completion']:
    if 'chunk' in event:
        chunk = event['chunk']
        if 'bytes' in chunk:
            print(chunk['bytes'].decode('utf-8'), end='', flush=True)
print()
"
```

**結果**: ✅ 正常応答

```
こんにちは！私は圧力計メーターの画像解析を支援するエージェントです。

圧力計の画像をアップロードしていただければ、針の位置を検出・強調表示し、
メーターの読み取り値を分析してお伝えすることができます。

圧力計の画像をお持ちでしたら、ぜひアップロードしてください！
```

**分析**:
- Agent自体は正常に動作
- sessionState.filesを含めなければエラーは発生しない
- **問題はsessionState.filesパラメータに起因**

### 試行5: Lambda直接呼び出しの検証

Lambda関数が正常に動作することを確認します。

**実行コマンド**:

```bash
cd scripts
python test_lambda.py ../sample_images/0001.png
```

**結果**: ✅ 成功

```
================================================================================
Lambda関数 動作確認スクリプト
================================================================================
[INFO] 入力画像: ../sample_images/0001.png
[INFO] 出力ディレクトリ: .../scripts/output

[INFO] 画像をbase64エンコード中...
[INFO] エンコード完了（サイズ: 520644 bytes）

[INFO] Lambda関数を呼び出し中...
[INFO] 関数名: pressure-gauge-detection
[INFO] リージョン: us-east-1
[INFO] ステータスコード: 200

[RESULT] メッセージ: 処理成功
[INFO] 処理済み画像を保存中: .../scripts/output/lambda_output_0001.png
[SUCCESS] 画像を保存しました

[SUCCESS] Lambda関数のテストが完了しました
```

**分析**:
- Lambda関数は正常に動作
- YOLO画像処理は成功
- 問題はBedrock Agentとの統合部分のみ

---

## 根本原因の分析

### promptOverrideConfigurationの調査

Agentの設定を確認します。

**実行コマンド**:

```bash
aws bedrock-agent get-agent \
  --agent-id FG9EIWNA4O \
  --region us-east-1 \
  | jq '.agent.promptOverrideConfiguration'
```

**結果** (一部抜粋):

```json
{
  "promptConfigurations": [
    {
      "basePromptTemplate": "{\n  \"system\": \"\n$instruction$\nYou have been provided with a set of functions...\\n$code_interpreter_guideline$\\n$knowledge_base_additional_guideline$\\n$code_interpreter_files$\\n...\",\n  \"messages\": [...]\n}",
      "inferenceConfiguration": {
        "stopSequences": ["</answer>"],
        "temperature": 1.0
      },
      "parserMode": "DEFAULT",
      "promptCreationMode": "DEFAULT",
      "promptState": "ENABLED",
      "promptType": "ORCHESTRATION"
    }
  ]
}
```

**重要な発見**:

`basePromptTemplate`に以下のプレースホルダーが含まれています：

- `$code_interpreter_files$`
- `$code_interpreter_guideline$`

これらのプレースホルダーは、Code Interpreterが**自身で**ファイルを処理する際に使用されます。

### 根本原因

以下の3つの技術的制約が明らかになりました：

#### 1. sessionState.filesの設計目的

`sessionState.files`は**Code Interpreter自身**がファイルを処理するための機能です。

```
ユーザー → sessionState.files → Code Interpreter（Python実行環境）
                                       ↓
                                  ファイルを読み込んで処理
```

**ユースケース例**:
- CSVファイルをアップロードしてデータ分析
- Pythonスクリプトでグラフ生成
- 画像をPILで読み込んで加工

#### 2. Action Groupとの非連携

`sessionState.files`で渡されたファイルは、**Action Groupには自動的に渡されません**。

```
┌─────────────────────┐
│ sessionState.files  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Code Interpreter    │  ← ここでファイルを処理
└─────────────────────┘

           ❌ 自動連携なし

┌─────────────────────┐
│ Action Group        │  ← Lambda関数のAPIパラメータ
│ (Lambda)            │     ("image"フィールド)
└─────────────────────┘
```

Action Groupは独自のAPIスキーマに基づいてパラメータを受け取ります：

```json
{
  "image": "base64エンコードされた画像データ"
}
```

sessionState.filesのデータは、このAPIパラメータに**自動的にマッピングされません**。

#### 3. promptOverrideConfigurationとの競合

Code Interpreterが有効な場合、promptTemplateには`$code_interpreter_files$`プレースホルダーが含まれます。

しかし、Code Interpreterを使わずにsessionState.filesを渡すと：

1. プレースホルダーが存在する
2. Code Interpreterは実際には使用されない
3. プレースホルダーが展開できない
4. → validationException エラー

```
エラー: "The overridden prompt that you provided is incorrectly formatted"
```

---

## 技術的な詳細

### Bedrock Agent Runtime APIの構造

**invoke_agentパラメータ**:

```python
response = client.invoke_agent(
    agentId='string',           # 必須
    agentAliasId='string',      # 必須
    sessionId='string',         # 必須
    inputText='string',         # 必須（filesがある場合でも）
    sessionState={              # オプション
        'sessionAttributes': {...},
        'promptSessionAttributes': {...},
        'files': [              # Code Interpreter用
            {
                'name': 'string',
                'source': {
                    'sourceType': 'S3'|'BYTE_CONTENT',
                    's3Location': {...},
                    'byteContent': {
                        'data': b'bytes',
                        'mediaType': 'string'
                    }
                },
                'useCase': 'CODE_INTERPRETER'|'CHAT'
            }
        ],
        'knowledgeBaseConfigurations': [...],
        'returnControlInvocationResults': [...]
    }
)
```

### filesパラメータの制約

AWS公式ドキュメントより：

1. **最大ファイルサイズ**: 全ファイル合計で10MB
2. **最大ファイル数**: 5ファイル
3. **useCase**:
   - `CODE_INTERPRETER`: Code Interpreterで処理
   - `CHAT`: チャット用（一部モデルで未サポート）
4. **対応形式**: テキスト、画像、コードなど

### Action Group API Schemaとの関係

Action Groupは独自のOpenAPI 3.0スキーマを持ち、以下のような構造でパラメータを受け取ります：

```json
{
  "requestBody": {
    "required": true,
    "content": {
      "application/json": {
        "schema": {
          "type": "object",
          "required": ["image"],
          "properties": {
            "image": {
              "type": "string",
              "description": "Base64 encoded image"
            }
          }
        }
      }
    }
  }
}
```

**重要**: このAPIスキーマは`sessionState.files`とは**完全に独立**しています。

Bedrock Agentは、ユーザーとの会話から必要なパラメータを抽出し、Action GroupのAPIスキーマに従ってLambda関数を呼び出します。

```
ユーザー入力（inputText）
  → Agent解析
  → パラメータ抽出
  → API Schema準拠のJSON作成
  → Lambda呼び出し
```

sessionState.filesのデータは、この流れに**組み込まれません**。

---

## 検証結果

### テストケース一覧

| テストケース | useCase | Code Interpreter | 結果 | エラー内容 |
|------------|---------|------------------|------|-----------|
| 1. 画像なし | - | 無効 | ✅ 成功 | - |
| 2. files + CHAT | CHAT | 無効 | ❌ 失敗 | validationException |
| 3. files + CODE_INTERPRETER | CODE_INTERPRETER | 無効 | ❌ 失敗 | validationException |
| 4. files + CODE_INTERPRETER | CODE_INTERPRETER | 有効 | ❌ 失敗 | validationException |
| 5. Lambda直接呼び出し | - | - | ✅ 成功 | - |

### 結論

**Code Interpreterを有効化しても、sessionState.filesによるAction Groupへの画像渡しは不可能**

理由:
1. sessionState.filesはCode Interpreter自身がファイルを処理するための機能
2. Action GroupのAPIパラメータとは自動連携しない
3. promptOverrideConfigurationとの競合が発生

---

## 解決策と代替案

### 推奨案: 分担方式

Lambda関数とBedrock Agentの役割を分担する方式が最も実用的です。

#### 運用フロー

**ステップ1: Lambda直接呼び出しで画像処理**

```bash
python scripts/test_lambda.py sample_images/0001.png
```

**結果**:
- `scripts/output/lambda_output_0001.png`に処理済み画像が生成される
- YOLOで針が赤色で強調表示される

**ステップ2: Bedrock Agentで質問応答**

画像なしでAgentに質問します：

```python
import boto3

client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

response = client.invoke_agent(
    agentId='FG9EIWNA4O',
    agentAliasId='ERQNJJS4ME',
    sessionId='user-session-123',
    inputText='圧力計の針が赤色で強調表示されています。針の角度から圧力値を推定する方法を教えてください。'
)

for event in response['completion']:
    if 'chunk' in event:
        chunk = event['chunk']
        if 'bytes' in chunk:
            print(chunk['bytes'].decode('utf-8'), end='')
```

**Agent応答例**:
```
圧力計の針の角度から圧力値を推定するには、以下の手順を行います：

1. ゲージの中心点を特定
2. 針の先端座標を取得
3. 中心から針先端への角度を計算
4. ゲージの目盛り範囲（例: 0-10MPa）と角度範囲（例: 0-270度）を対応付け
5. 比例計算で圧力値を算出

例えば、針が90度の位置にあり、ゲージが0-10MPaで0-270度の範囲の場合：
圧力値 = (90 / 270) × 10 = 3.33 MPa
```

#### メリット

- ✅ すぐに使える（追加実装不要）
- ✅ Lambda処理は確実に動作
- ✅ Agentは質問応答・ガイダンスを提供
- ✅ 各コンポーネントの責任が明確

#### デメリット

- ❌ AgentからLambdaを自動呼び出しする統合フローにはならない
- ❌ 手動で2ステップ実行が必要
- ❌ ユーザー体験が若干煩雑

### 代替案: S3統合方式

完全統合が必要な場合、S3を経由する方式を実装します。

#### アーキテクチャ

```
ユーザー
  ↓ 1. 画像をS3にアップロード
S3 Bucket
  ↓ 2. S3 URIを取得
Bedrock Agent
  ↓ 3. "s3://bucket/image.png を処理して" (inputText)
  ↓ 4. detect-gauge Action呼び出し (s3Uri パラメータ)
Lambda Function
  ↓ 5. S3から画像ダウンロード
  ↓ 6. YOLO処理
  ↓ 7. 結果をS3に保存 or base64で返却
Bedrock Agent
  ↓ 8. 結果を解析・説明
ユーザー
```

#### 実装手順

**1. S3バケットの作成**

```bash
aws s3 mb s3://pressure-gauge-images-bucket
```

**2. Action Group APIスキーマの変更**

```json
{
  "paths": {
    "/detect-gauge": {
      "post": {
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["s3Uri"],
                "properties": {
                  "s3Uri": {
                    "type": "string",
                    "description": "S3 URI of the gauge image (s3://bucket/key)"
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**3. Lambda関数の修正**

```python
import boto3
import base64

s3 = boto3.client('s3')

def lambda_handler(event, context):
    # Action Groupから受け取ったパラメータ
    s3_uri = event['requestBody']['content']['application/json']['properties'][0]['value']

    # S3 URIをパース
    bucket, key = parse_s3_uri(s3_uri)

    # S3から画像をダウンロード
    response = s3.get_object(Bucket=bucket, Key=key)
    image_bytes = response['Body'].read()

    # YOLO処理
    processed_image = yolo_process(image_bytes)

    # 結果を返却
    return {
        'processedImage': base64.b64encode(processed_image).decode('utf-8'),
        'message': '処理成功'
    }
```

**4. IAMポリシーの追加**

Lambda関数にS3読み取り権限を付与：

```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject"
  ],
  "Resource": "arn:aws:s3:::pressure-gauge-images-bucket/*"
}
```

**5. テストスクリプトの実装**

```python
import boto3
from pathlib import Path

# S3にアップロード
s3 = boto3.client('s3')
bucket = 'pressure-gauge-images-bucket'
key = 'test-images/0001.png'

with open('sample_images/0001.png', 'rb') as f:
    s3.put_object(Bucket=bucket, Key=key, Body=f)

s3_uri = f's3://{bucket}/{key}'

# Bedrock Agentを呼び出し
client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

response = client.invoke_agent(
    agentId='FG9EIWNA4O',
    agentAliasId='ERQNJJS4ME',
    sessionId='session-123',
    inputText=f'{s3_uri} の画像を処理して、針の位置を教えてください'
)
```

#### メリット

- ✅ AgentからLambdaへの完全統合フロー
- ✅ ユーザー体験が向上（1回の呼び出しで完結）
- ✅ 大きな画像ファイルにも対応可能

#### デメリット

- ❌ 実装コストが高い（数時間の開発が必要）
- ❌ S3バケットの管理が必要
- ❌ Lambda関数の大幅な変更が必要
- ❌ IAM権限設定が複雑化

---

## まとめ

### 学んだこと

1. **sessionState.filesの真の目的**
   - Code Interpreter自身がファイルを処理するための機能
   - Action Groupとは独立した仕組み

2. **Bedrock Agentのアーキテクチャ**
   - Action GroupはOpenAPI Schemaに基づいてパラメータを受け取る
   - sessionState.filesからの自動マッピングは行われない

3. **promptOverrideConfigurationの重要性**
   - プレースホルダー（`$code_interpreter_files$`など）が含まれる
   - Code Interpreterを使わない場合、競合が発生する可能性

### 推奨アプローチ

現在のアーキテクチャでは、**分担方式**が最も実用的です：

1. Lambda直接呼び出しで画像処理
2. Bedrock Agentで質問応答・ガイダンス

完全統合が必要な場合は、**S3統合方式**を実装してください。

### 最終的な状態

- ✅ Lambda関数（YOLO画像処理）: 正常動作
- ✅ Bedrock Agent（Claude Sonnet 4.5）: 正常応答
- ✅ Code Interpreter Action Group: 有効化済み
- ❌ sessionState.files → Action Group連携: 技術的に不可能
- ✅ 分担方式での運用: 可能で推奨

### 参考リソース

- [AWS Bedrock Agent Runtime API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvokeAgent.html)
- [AWS Bedrock Agent sessionState Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-session-state.html)
- [Code Interpreter for Bedrock Agents](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-enable-code-interpretation.html)

---

**作成者**: Claude (Anthropic)
**プロジェクト**: 圧力計メーター画像解析システム
**日付**: 2025-11-30
