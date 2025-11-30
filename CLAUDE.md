# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

圧力計メーター針をYOLOv8で検出し、Claude Sonnet 4.5 (AWS Bedrock) で画像解析を行う自動読み取りシステム。AWS Lambda（コンテナイメージ形式）とAWS CDKでサーバーレス実装。

## プロジェクト構成

```
aws-pressure-gauge-reader/         # メインプロジェクト
├── cdk/                           # AWS CDKプロジェクト
│   ├── bin/                       # CDKエントリーポイント
│   ├── lib/                       # CDKスタック定義
│   │   └── cdk-stack.ts          # Lambda関数、ECR、IAM設定
│   └── lambda/                    # Lambda関数コード
│       ├── Dockerfile             # コンテナイメージ定義
│       ├── lambda_function.py     # Lambda関数ハンドラー
│       ├── yolo_processor.py      # YOLO処理ロジック
│       ├── best.pt                # YOLOv8モデル（6.7MB）
│       └── requirements.txt       # Python依存パッケージ
├── scripts/                       # テストスクリプト
│   ├── test.py                    # Lambda動作確認スクリプト
│   ├── user_prompt.txt            # ユーザープロンプト
│   ├── system_prompt.txt          # システムプロンプト
│   └── requirements.txt           # Python依存パッケージ
├── docs/                          # 技術ドキュメント（詳細は下記参照）
└── sample_images/                 # サンプル画像
```

## アーキテクチャ

```
Client (test.py)
  ↓ {"image": "base64...", "userPrompt": "...", "systemPrompt": "...", "preprocessImage": true/false}
Lambda関数 (us-east-1)
  ├─ YOLO前処理（針を赤色で強調） - optional
  └─ Bedrock LLM呼び出し（Claude Sonnet 4.5）
  ↓ {"llmResponse": "...", "processedImage": "base64...", "yoloMessage": "..."}
Client
  ├─ LLM回答を表示
  └─ 前処理済み画像を保存
```

### 技術スタック

- **Lambda関数**: YOLOv8による針検出 + Claude Sonnet 4.5による解析（コンテナイメージ形式、Python 3.11）
- **ECRリポジトリ**: Dockerイメージの保存（`pressure-gauge-detection`）
- **IAMロール**: Lambda実行ロール（Bedrock呼び出し権限を含む）
- **Bedrock Model**: Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)

## セットアップと開発コマンド

### 前提条件

- Node.js 18以上
- Docker
- AWS CLI（認証情報設定済み）
- AWS CDK
- Bedrock Model Access（us-east-1でClaude Sonnet 4.5へのアクセス有効化）

### CDKプロジェクトのセットアップ

```bash
cd aws-pressure-gauge-reader/cdk

# 依存パッケージのインストール
npm install

# CDKブートストラップ（初回のみ）
npx cdk bootstrap aws://<YOUR_AWS_ACCOUNT_ID>/us-east-1

# スタックの検証
npx cdk synth

# デプロイ
npx cdk deploy

# クリーンアップ
npx cdk destroy
```

### テストスクリプトのセットアップと実行

```bash
cd aws-pressure-gauge-reader/scripts

# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate  # macOS/Linux
# または venv\Scripts\activate  # Windows

# 依存パッケージをインストール
pip install -r requirements.txt

# Lambda関数をテスト（YOLO前処理あり）
python test.py ../sample_images/0001.png

# YOLO前処理をスキップ（オリジナル画像をそのままLLMに送信）
python test.py ../sample_images/0001.png --no-preprocess

# カスタムプロンプトを使用
python test.py ../sample_images/0002.png \
  --user-prompt ./my_user_prompt.txt \
  --system-prompt ./my_system_prompt.txt
```

## Lambda関数の処理フロー

1. **入力受付**: Base64エンコードされた画像を受け取る
2. **YOLO前処理**（オプション）:
   - YOLOv8で針をセグメンテーション
   - 針を赤色で強調表示
   - 針の先端に赤色三角形マーカーを追加
3. **Bedrock LLM呼び出し**:
   - 前処理済み画像（またはオリジナル画像）をClaude Sonnet 4.5に送信
   - プロンプトとともに画像解析を実行
4. **結果返却**: LLMの回答と前処理済み画像をJSON形式で返す

### グローバル変数によるコールドスタート対策

Lambda関数は以下をグローバル変数でキャッシュ:
- `processor`: YOLOプロセッサー（モデルロード時間を節約）
- `bedrock_client`: Bedrock Runtimeクライアント

## Lambda環境設定

- **リージョン**: us-east-1
- **メモリ**: 3GB
- **タイムアウト**: 120秒
- **環境変数**:
  - `MODEL_PATH`: `/opt/ml/model/best.pt`（Dockerイメージ内のモデルパス）
  - `BEDROCK_REGION`: `us-east-1`
  - `CONF_THRESHOLD`: `0.65`（YOLO信頼度閾値）
  - `IOU_THRESHOLD`: `0.5`（YOLO IOU閾値）

## YOLO処理の仕組み

### 針の検出ロジック（yolo_processor.py）

- ゲージ中心を画像中心と仮定
- 針の先端: 中心から最も遠いピクセル
- 針の基部: 中心から最も近いピクセル
- **注意**: 中心座標が画像中心と異なる場合は、手動指定が必要

### 視覚化モード

現在の実装では `triangle` モードを使用:
- 赤色で針をオーバーレイ
- 針の先端に赤色三角形マーカーを配置

## Bedrockモデル設定

### Claude Sonnet 4.5の使用

- **モデルID**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (inference profile)
- **リージョン制約**: us-east-1でのみ利用可能
- **IAMポリシー**: ワイルドカード（`arn:aws:bedrock:*::...`）で全リージョンを許可

### プロンプトファイルのカスタマイズ

テストスクリプトは以下のファイルを使用:
- **user_prompt.txt**: LLMへの質問内容
- **system_prompt.txt**: LLMの役割・振る舞いの定義

## トラブルシューティング

### Bedrock Model Accessエラー

```
Error: AccessDeniedException
```

**解決方法**: AWS Console → Amazon Bedrock → Model access（us-east-1）で Claude Sonnet 4.5 のアクセスを有効化

### Dockerビルドエラー

**確認事項**:
1. Dockerが起動していること
2. `cdk/lambda/best.pt` が存在すること（約6.7MB）
3. ディスク容量が十分であること

### リージョンエラー

```
Error: us-east-2 への accessDeniedException
```

**解決方法**:
- Lambda環境変数 `BEDROCK_REGION=us-east-1` が設定されていることを確認
- IAMポリシーで全リージョンのワイルドカード（`arn:aws:bedrock:*::...`）が許可されていることを確認
- 詳細は [docs/02_implementation/02_claude-sonnet-4.5-on-cdk.md](docs/02_implementation/02_claude-sonnet-4.5-on-cdk.md) を参照

## コスト概算（月100回実行の場合）

- Lambda: ~$0.50
- ECR: ~$0.15
- Bedrock: ~$2.00
- **合計**: 約 $2.65/月

## 技術ドキュメント

詳細は [docs/](docs/) を参照:

### 00_overview - プロジェクト概要
現在、このディレクトリにドキュメントはありません。

### 01_architecture - アーキテクチャ設計
- **[なぜBedrock Agentを使わないのか](docs/01_architecture/01_why-not-bedrock-agent.md)** - アーキテクチャ選択の理由
- **[Bedrock Agent画像連携の制約](docs/01_architecture/02_bedrock-agent-image-limitation.md)** - sessionState.filesの試行錯誤の記録

### 02_implementation - 実装ガイド
- **[Lambda機械学習実装ガイド](docs/02_implementation/01_lambda-ml-implementation-guide.md)** - Docker vs Lambda Layer、パフォーマンス最適化
- **[Claude Sonnet 4.5利用ガイド](docs/02_implementation/02_claude-sonnet-4.5-on-cdk.md)** - CDK制約、Inference Profile、IAMポリシー設定

## 重要な注意点

- YOLOモデルファイル（best.pt）は必須。Dockerイメージ内に `/opt/ml/model/best.pt` として配置
- Bedrock Model Accessは事前にus-east-1リージョンで有効化が必要
- 入出力画像サイズに注意（Lambdaペイロード制限: 6MB）
- コールドスタート時間: 初回実行は10-30秒程度（モデルロード時間）
