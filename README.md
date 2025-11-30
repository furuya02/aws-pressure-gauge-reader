# AWS Pressure Gauge Reader

圧力計メーター針をYOLOv8で検出し、Claude Sonnet 4.5 (AWS Bedrock) で画像解析を行う自動読み取りシステムです。

## 特徴

- 🎯 **YOLOv8セグメンテーション**: 圧力計の針を高精度で検出
- 🤖 **Claude Sonnet 4.5**: AWS Bedrockを使用したAI画像解析
- ☁️ **サーバーレス**: AWS Lambdaでの完全サーバーレス実装
- 🐳 **Dockerコンテナ**: 10GBまでのモデルをサポート
- 📊 **前処理画像の返却**: AI解析結果と前処理済み画像の両方を取得可能

## アーキテクチャ

```
Client (test.py)
  ↓ {"image": "base64...", "userPrompt": "...", "systemPrompt": "...", "preprocessImage": true/false}
Lambda関数 (us-east-1)
  ├─ YOLO前処理（針を赤色で強調）- optional
  └─ Bedrock LLM呼び出し（Claude Sonnet 4.5）
  ↓ {"llmResponse": "...", "processedImage": "base64...", "yoloMessage": "..."}
Client
  ├─ LLM回答を表示
  └─ 前処理済み画像を保存
```

### なぜBedrock Agentを使わないのか？

詳細は [CLAUDE.md](CLAUDE.md) および [docs/01_architecture/01_why-not-bedrock-agent.md](docs/01_architecture/01_why-not-bedrock-agent.md) を参照してください。

**主な理由:**
1. **画像連携の制約**: `sessionState.files` はAction Groupに画像を渡せない
2. **非効率性**: 単一アクションではAgentのオーバーヘッド（約1.3秒）が無駄
3. **シンプルさ**: Lambda直接呼び出しの方が理解しやすく、デバッグも容易

## 構成要素

- **Lambda関数**: YOLOv8による針検出 + Claude Sonnet 4.5による解析（コンテナイメージ形式）
- **ECRリポジトリ**: Dockerイメージの保存
- **IAMロール**: Lambda実行ロール（Bedrock呼び出し権限を含む）

## 前提条件

1. **AWS CLI**がインストール・設定されていること
2. **Node.js 18以上**がインストールされていること
3. **Docker**がインストールされていること
4. **AWS CDK**がインストールされていること
5. **Bedrock Model Access**でClaude Sonnet 4.5へのアクセスが有効化されていること（us-east-1）

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd cdk
npm install
```

### 2. AWS認証情報の設定

```bash
aws configure
# または環境変数を設定
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

### 3. CDKのブートストラップ（初回のみ）

```bash
npx cdk bootstrap aws://<YOUR_AWS_ACCOUNT_ID>/us-east-1
```

## デプロイ

### 1. CDK Synthで検証

```bash
npx cdk synth
```

### 2. デプロイ実行

```bash
npx cdk deploy
```

**注意**: 初回デプロイ時は、Dockerイメージのビルドに時間がかかります（10-20分程度）。

デプロイが完了すると、以下の情報が出力されます:
- `ECRRepositoryUri`: ECRリポジトリのURI
- `LambdaFunctionName`: Lambda関数名（デフォルト: `pressure-gauge-detection`）
- `LambdaFunctionArn`: Lambda関数のARN

## 使用方法

### プロンプトファイルの準備

テストスクリプトは、`scripts/`ディレクトリにある以下のプロンプトファイルを使用します：

- **user_prompt.txt**: ユーザープロンプト（LLMへの質問内容）
- **system_prompt.txt**: システムプロンプト（LLMの役割・振る舞いの定義）

これらのファイルは自由に編集可能です。詳細は [scripts/README.md](scripts/README.md#プロンプトファイル) を参照してください。

### テストスクリプト経由（推奨）

```bash
cd scripts

# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows

# 依存パッケージをインストール
pip install -r requirements.txt

# テスト実行
python test.py ../sample_images/0001.png
```

**出力例:**
```
[YOLO処理] 針検出成功: 1個の針を検出しました

[LLM解析結果]
--------------------------------------------------------------------------------
この圧力計の針は **約0.05 MPa** を指しています。

針は0と0.2の間の、0に近い位置を示しており、目盛りから判断すると
**0.05 MPa前後** の値を示していると読み取れます。
--------------------------------------------------------------------------------

[INFO] 前処理済み画像を保存中: output/0001_processed.png
[SUCCESS] テストが完了しました
```

### AWS CLI経由

```bash
# ペイロードを準備
echo '{
  "image": "'"$(base64 -i sample_images/0001.png)"'",
  "userPrompt": "この圧力計を読み取ってください。",
  "systemPrompt": "あなたは圧力計の画像から正確な数値を読み取る専門家です。画像を慎重に観察して、針の位置を正確に読み取ってください。",
  "preprocessImage": true
}' > payload.json

# Lambda関数を呼び出し
aws lambda invoke \
  --function-name pressure-gauge-detection \
  --payload file://payload.json \
  --region us-east-1 \
  output.json

# 結果を確認
cat output.json | jq -r '.body | fromjson | .llmResponse'

# 前処理をスキップする場合（オリジナル画像をそのままLLMに送信）
echo '{
  "image": "'"$(base64 -i sample_images/0001.png)"'",
  "userPrompt": "この圧力計を読み取ってください。",
  "systemPrompt": "あなたは圧力計の画像から正確な数値を読み取る専門家です。",
  "preprocessImage": false
}' > payload.json
```

## デプロイ後の設定

### Bedrock Model Accessの有効化

1. AWS Console → Amazon Bedrock → Model access
2. **Claude Sonnet 4.5** (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) を選択
3. **Request access** をクリック
4. 承認されるまで待機（通常は即座に承認される）

## トラブルシューティング

### デプロイエラー: Bedrock Model Accessがない

```
Error: AccessDeniedException
```

**解決方法:**
上記の「Bedrock Model Accessの有効化」を実施してください。

### Dockerビルドエラー

```
Error: Docker build failed
```

**解決方法:**
1. Dockerが起動していることを確認
2. `cdk/lambda/best.pt`が存在することを確認（約6.7MB）
3. ディスク容量を確認

### リージョンエラー

```
Error: us-east-2 への accessDeniedException
```

**解決方法:**
- Lambda環境変数 `BEDROCK_REGION=us-east-1` が設定されていることを確認
- IAMポリシーで全リージョンのワイルドカード（`arn:aws:bedrock:*::...`）が許可されていることを確認
- 詳細は [docs/02_implementation/02_claude-sonnet-4.5-on-cdk.md](docs/02_implementation/02_claude-sonnet-4.5-on-cdk.md) を参照

## クリーンアップ

すべてのリソースを削除する場合:

```bash
npx cdk destroy
```

**注意**: ECRリポジトリ内の画像も自動削除されます（`autoDeleteImages: true`設定のため）。

## コスト

主なコスト要素:
- **Lambda実行**: メモリ3GB × 実行時間（約2-5秒）
- **ECRストレージ**: Dockerイメージサイズ（約1.5GB）
- **Bedrock**: Claude Sonnet 4.5の使用量（入力・出力トークン数）

**概算（月100回実行の場合）:**
- Lambda: ~$0.50
- ECR: ~$0.15
- Bedrock: ~$2.00
- **合計: 約 $2.65/月**

## 技術ドキュメント

開発者向けの詳細情報は [CLAUDE.md](CLAUDE.md) を参照してください。

詳細な技術情報は [docs/](docs/) ディレクトリを参照してください:

### アーキテクチャ設計
- **[Bedrock Agent不使用の理由](docs/01_architecture/01_why-not-bedrock-agent.md)**: アーキテクチャ選択の詳細な理由
- **[Bedrock Agent画像連携の制約](docs/01_architecture/02_bedrock-agent-image-limitation.md)**: sessionState.filesの試行錯誤の全記録

### 実装ガイド
- **[Lambda機械学習実装ガイド](docs/02_implementation/01_lambda-ml-implementation-guide.md)**: Docker vs Lambda Layer、パフォーマンス最適化、トラブルシューティング
- **[Claude Sonnet 4.5利用ガイド](docs/02_implementation/02_claude-sonnet-4.5-on-cdk.md)**: CDK制約、Inference Profile、IAMポリシー設定

## プロジェクト構成

```
.
├── cdk/                          # AWS CDKプロジェクト
│   ├── bin/                      # CDKエントリーポイント
│   ├── lib/                      # CDKスタック定義
│   └── lambda/                   # Lambda関数コード
│       ├── Dockerfile            # コンテナイメージ定義
│       ├── lambda_function.py    # Lambda関数ハンドラー
│       ├── yolo_processor.py     # YOLO処理ロジック
│       ├── best.pt               # YOLOv8モデル（6.7MB）
│       └── requirements.txt      # Python依存パッケージ
├── docs/                         # 技術ドキュメント
├── scripts/                      # テストスクリプト
│   ├── test.py                   # Lambda動作確認スクリプト
│   ├── user_prompt.txt           # ユーザープロンプト
│   ├── system_prompt.txt         # システムプロンプト
│   └── requirements.txt          # Python依存パッケージ
└── sample_images/                # サンプル画像
```

## ライセンス

MIT License

## 貢献

Issue や Pull Request を歓迎します。

## 参考リンク

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
