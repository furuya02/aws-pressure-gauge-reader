# Bedrock Agentを利用しない理由

## 目次

1. [概要](#概要)
2. [試行錯誤の経緯](#試行錯誤の経緯)
3. [問題1: Actionに画像が連携できない](#問題1-actionに画像が連携できない)
4. [問題2: 単一アクションでの非効率性](#問題2-単一アクションでの非効率性)
5. [最終的なアーキテクチャ選択](#最終的なアーキテクチャ選択)
6. [メリット・デメリット比較](#メリットデメリット比較)
7. [まとめ](#まとめ)

## 概要

本プロジェクトでは、当初AWS Bedrock Agentを使用する予定でしたが、以下の2つの理由により、最終的に**Lambda関数から直接Bedrock LLMを呼び出すシンプルなアーキテクチャ**に変更しました。

### 主な理由

1. **Actionに画像が連携できない** - `sessionState.files`の制限
2. **単一アクションでの非効率性** - Agentのオーバーヘッドが無駄

## 試行錯誤の経緯

### 当初の計画

```
ユーザー
  ↓ テキスト + 画像
Bedrock Agent
  ↓ 画像をActionに連携
Lambda (Action Group)
  ↓ YOLO前処理
Bedrock Agent
  ↓ 前処理済み画像 + LLM解析
ユーザー
```

**期待していた動作:**
1. ユーザーが画像とテキストをBedrock Agentに送信
2. Agent が画像をAction Group（Lambda関数）に渡す
3. Lambda が YOLO前処理を実行
4. Agent が前処理済み画像をLLMに渡して解析
5. LLMの結果をユーザーに返す

### 実際の問題

しかし、実装を進めると**画像をActionに連携できない**ことが判明しました。

## 問題1: Actionに画像が連携できない

### sessionState.filesの制限

Bedrock Agentには`sessionState.files`というファイル渡し機能がありますが、これは**Code Interpreter専用**の機能であり、**Action Groupには連携されません**。

#### 試行1: sessionState.filesでの画像送信

```python
# テストコード
response = bedrock_agent_runtime.invoke_agent(
    agentId=agent_id,
    agentAliasId=agent_alias_id,
    sessionId=session_id,
    inputText="この圧力計のメーターを読み取ってください",
    sessionState={
        'files': [
            {
                'name': '0001.png',
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

**結果:**
```
validationException: The overridden prompt that you provided is incorrectly formatted.
```

#### 試行2: Code Interpreter機能の有効化

Code Interpreter機能を有効化すれば動くのではないかと考えました。

```bash
# AWS CLIでCode Interpreter Action Groupを作成
aws bedrock-agent create-agent-action-group \
  --agent-id FG9EIWNA4O \
  --agent-version DRAFT \
  --action-group-name CodeInterpreterAction \
  --action-group-state ENABLED \
  --parent-action-group-signature AMAZON.CodeInterpreter
```

```python
# useCase を CODE_INTERPRETER に変更
sessionState={
    'files': [{
        # ...
        'useCase': 'CODE_INTERPRETER'
    }]
}
```

**結果:**
```
validationException: The overridden prompt that you provided is incorrectly formatted.
```

同じエラーが発生しました。

### 根本原因の分析

詳細な調査の結果、以下の3つの技術的制約が判明しました：

#### 制約1: sessionState.filesの設計目的

`sessionState.files`は、**Code Interpreter自身がファイルを処理する**ための機能です。

```
sessionState.files の用途:
- Code Interpreterがファイルを読み込んで分析
- Code Interpreterがデータを可視化
- Code Interpreterがファイルを生成

❌ Action Groupにファイルを渡す用途ではない
```

#### 制約2: Action Group APISchemaとsessionStateの独立性

Action GroupのAPIスキーマパラメータと`sessionState.files`は**完全に独立**しています。

```json
// Action Group APIスキーマ (OpenAPI 3.0)
{
  "parameters": [
    {
      "name": "image",
      "in": "query",
      "schema": {"type": "string"},
      "required": true
    }
  ]
}
```

```python
# sessionState.files
sessionState = {
  'files': [...]  # ← これはAPIスキーマのパラメータに自動マッピングされない
}
```

**自動マッピングは行われません。**

#### 制約3: promptOverrideConfigurationとの競合

Bedrock AgentのpromptOverrideConfigurationには`$code_interpreter_files$`というプレースホルダーがあります。

```
$code_interpreter_files$プレースホルダー:
- Code Interpreterが処理したファイル情報を挿入
- Action Groupには無関係
- このプレースホルダーがあるとsessionState.filesの使用が強制される
- しかしAction Groupでは使えないため、エラーになる
```

### 結論

**sessionState.filesを使ってAction Groupに画像を渡すことは不可能**です。

詳細な試行錯誤の記録は [`bedrock-agent-image-limitation.md`](./bedrock-agent-image-limitation.md) を参照してください。

## 問題2: 単一アクションでの非効率性

### 本プロジェクトの要件

本プロジェクトでは、以下の処理を行います：

1. **YOLO前処理**: 圧力計画像から針をセグメンテーション
2. **LLM解析**: 前処理済み画像を解析して圧力値を読み取り

**重要な点:** アクションは**1種類のみ**です。

### Bedrock Agentのオーバーヘッド

Bedrock Agentを使用すると、以下のオーバーヘッドが発生します：

#### 処理フロー

```
1. ユーザー → Agent:              ~100ms (ネットワーク)
2. Agent → プロンプト生成:         ~500ms (LLM呼び出し)
3. Agent → Action決定:             ~300ms (LLM呼び出し)
4. Agent → Lambda呼び出し:         ~100ms (ネットワーク)
5. Lambda → YOLO処理:              ~2000ms
6. Lambda → Agent:                 ~100ms (ネットワーク)
7. Agent → 結果統合:               ~300ms (LLM呼び出し)
8. Agent → LLM解析:                ~5000ms (画像解析)
9. Agent → ユーザー:               ~100ms (ネットワーク)
-----------------------------------------------------------
合計:                              ~8500ms
```

#### Lambda直接呼び出しの場合

```
1. ユーザー → Lambda:              ~100ms (ネットワーク)
2. Lambda → YOLO処理:              ~2000ms
3. Lambda → Bedrock LLM呼び出し:   ~5000ms (画像解析)
4. Lambda → ユーザー:              ~100ms (ネットワーク)
-----------------------------------------------------------
合計:                              ~7200ms
```

**削減時間: 約1.3秒（15%改善）**

### 複雑性の増加

Bedrock Agentを使用すると、以下の複雑性が追加されます：

#### 必要なリソース

- ✅ Lambda関数（Action Group）
- ✅ Bedrock Agent
- ✅ Bedrock Agent Alias
- ✅ IAM Role（Agent用）
- ✅ IAM Role（Lambda用）
- ✅ Action Group APIスキーマ（OpenAPI 3.0）
- ✅ Agent Instructionプロンプト
- ✅ promptOverrideConfiguration（オプション）

#### トラブルシューティングの困難さ

```
エラー発生時の原因特定:
- Agentのプロンプト生成の問題？
- Action Groupの呼び出し設定の問題？
- APIスキーマの問題？
- Lambda関数の問題？
- LLM呼び出しの問題？

デバッグ箇所が多すぎる
```

### Agentが有効なケース

Bedrock Agentは以下のような場合に有効です：

#### 複数アクションの調整

```
例: カスタマーサポートボット

ユーザー: 「注文をキャンセルして、返金してください」
  ↓
Agent: アクション1「注文キャンセル」を実行
Agent: アクション2「返金処理」を実行
Agent: 両方の結果を統合してレスポンス
```

**本プロジェクトには該当しない** - アクションは1種類のみ

#### 動的なツール選択

```
例: データ分析アシスタント

ユーザー: 「売上データを可視化してください」
  ↓
Agent: データ取得ツールを選択
Agent: グラフ生成ツールを選択
Agent: 結果を統合
```

**本プロジェクトには該当しない** - 処理フローは固定

#### 会話の文脈管理

```
例: 対話型FAQ

ユーザー: 「配送状況は？」
Agent: 注文番号を確認
ユーザー: 「12345です」
Agent: 注文番号12345の配送状況を検索
```

**本プロジェクトには該当しない** - 単発の画像解析のみ

## 最終的なアーキテクチャ選択

### 選択: Lambda直接呼び出し方式

```
Client (test.py)
  ↓ {"image": "base64...", "text": "..."}
Lambda (us-east-1)
  ├─ YOLO前処理（針を赤色で強調）
  └─ Bedrock LLM呼び出し（Claude Sonnet 4.5）
  ↓ {"llmResponse": "...", "processedImage": "base64...", "yoloMessage": "..."}
Client
  ├─ LLM回答を表示
  └─ 前処理済み画像を保存
```

### 実装

#### Lambda関数

```python
def lambda_handler(event, context):
    # 1. 入力取得
    image_base64 = event["image"]
    user_text = event["text"]

    # 2. YOLO前処理
    proc = initialize_processor()
    processed_image, yolo_message = proc.process_image(image)

    # 3. Bedrock LLM呼び出し
    bedrock = initialize_bedrock_client()
    llm_response = invoke_bedrock_model(
        client=bedrock,
        processed_image_base64=processed_image_base64,
        user_text=user_text
    )

    # 4. レスポンス返却
    return {
        "statusCode": 200,
        "body": json.dumps({
            "llmResponse": llm_response,
            "processedImage": processed_image_base64,
            "yoloMessage": yolo_message
        })
    }
```

#### CDKスタック

```typescript
const lambdaFunction = new lambda.DockerImageFunction(this, 'Function', {
  code: lambda.DockerImageCode.fromImageAsset('./lambda'),
  memorySize: 3008,
  timeout: cdk.Duration.seconds(120),
  environment: {
    MODEL_PATH: '/opt/ml/model/best.pt',
    BEDROCK_REGION: 'us-east-1',
  },
});

// Lambda → Bedrock権限
lambdaFunction.addToRolePolicy(new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: ['bedrock:InvokeModel'],
  resources: [
    `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-5-*`,
    // ...
  ],
}));
```

## メリット・デメリット比較

### Bedrock Agent方式

#### メリット

- ✅ 複数アクションの調整が容易
- ✅ 会話の文脈を自動管理
- ✅ ツール選択をLLMに委ねられる
- ✅ プロンプトエンジニアリングの柔軟性

#### デメリット

- ❌ **画像をActionに渡せない**（致命的）
- ❌ 単一アクションでは非効率（約1.3秒のオーバーヘッド）
- ❌ デバッグが複雑
- ❌ リソースが多く管理が煩雑
- ❌ CDK L2 Constructが未提供（2.220.0時点）
- ❌ コストが高い（Agent使用料 + Lambda + Bedrock LLM）

### Lambda直接呼び出し方式

#### メリット

- ✅ **シンプルで理解しやすい**
- ✅ **高速**（約15%高速化）
- ✅ **デバッグが容易**（Lambda Logsのみ確認）
- ✅ **低コスト**（Agent使用料が不要）
- ✅ 前処理済み画像を確認できる
- ✅ CDKでの実装が簡単

#### デメリット

- ❌ 複数アクションの調整は手動実装が必要
- ❌ 会話の文脈管理は自前実装が必要
- ❌ ツール選択ロジックを手動実装が必要

**本プロジェクトでは該当しない** - アクションが1種類のみのため

## まとめ

### Bedrock Agentを使用しなかった理由

1. **技術的制約**: `sessionState.files`はAction Groupに画像を渡せない
2. **非効率性**: 単一アクションでは Agent のオーバーヘッドが無駄
3. **複雑性**: デバッグやメンテナンスが困難
4. **コスト**: Agent使用料が追加で発生

### Lambda直接呼び出しを選択した理由

1. **シンプル**: 理解しやすく、メンテナンスが容易
2. **高速**: 約15%の性能改善
3. **低コスト**: Agent使用料が不要
4. **柔軟性**: 前処理済み画像を確認可能

### 推奨される使い分け

#### Bedrock Agentが適している場合

- ✅ 複数のアクション（ツール）を組み合わせる必要がある
- ✅ 動的なツール選択が必要
- ✅ 会話の文脈を長期間保持する必要がある
- ✅ **画像をActionに渡す必要がない**

#### Lambda直接呼び出しが適している場合（本プロジェクト）

- ✅ アクションが1種類のみ
- ✅ 処理フローが固定
- ✅ シンプルさを重視
- ✅ 低レイテンシが重要
- ✅ **画像を扱う必要がある**

### 参考ドキュメント

- [Bedrock Agent画像連携の詳細な調査](./bedrock-agent-image-limitation.md) - sessionState.filesの試行錯誤の全記録
- [Lambda機械学習実装ガイド](./lambda-ml-implementation-guide.md) - Lambda環境での実装詳細
- [Claude Sonnet 4.5利用ガイド](./claude-sonnet-4.5-on-cdk.md) - Bedrock LLM直接呼び出しの方法

本プロジェクトのユースケースでは、**Lambda直接呼び出し方式が最適**です。
