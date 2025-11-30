# Test Scripts for Pressure Gauge Detection

このディレクトリには、圧力計メーター読み取りシステムの動作確認用スクリプトが含まれています。

## システム概要

このシステムは以下の処理を行います：
1. **YOLO前処理**: 圧力計の画像から針をセグメンテーションし、赤色で強調表示
2. **LLM解析**: 前処理済み画像をClaude Sonnet 4.5に送信し、メーター値を読み取り
3. **結果返却**: LLMの回答と前処理済み画像の両方を返却

## アーキテクチャ

```
Client (test.py)
  ↓ {"image": "base64...", "userPrompt": "...", "systemPrompt": "...", "preprocessImage": true/false}
Lambda (us-east-1)
  ├─ YOLO前処理（針を赤色で強調）- optional
  └─ Bedrock LLM呼び出し（Claude Sonnet 4.5）
  ↓ {"llmResponse": "...", "processedImage": "base64...", "yoloMessage": "..."}
Client
  ├─ LLM回答を表示
  └─ 前処理済み画像を保存
```

## 前提条件

1. **AWS認証情報が設定されていること**
   ```bash
   aws configure
   # または環境変数を設定
   export AWS_ACCESS_KEY_ID=...
   export AWS_SECRET_ACCESS_KEY=...
   export AWS_SESSION_TOKEN=...  # 一時認証の場合
   export AWS_DEFAULT_REGION=us-east-1
   ```

2. **Python仮想環境のセットアップと依存パッケージのインストール**
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
   ```

3. **CDKスタックがデプロイ済みであること**
   ```bash
   cd ../cdk
   ./node_modules/.bin/cdk deploy
   ```
   デプロイ時に出力される `LambdaFunctionName` をメモしてください（デフォルト: `pressure-gauge-detection`）

## プロンプトファイル

システムには2つのプロンプトファイルが用意されています：

### user_prompt.txt

ユーザープロンプト（LLMへの質問内容）を定義します。

**デフォルト内容:**
```
User: この圧力計を読み取ってください。
```

### system_prompt.txt

システムプロンプト（LLMの役割・振る舞いの定義）を定義します。

**デフォルト内容:**
```
あなたは圧力計の画像から正確な数値を読み取る専門家です。画像を慎重に観察して、針の位置を正確に読み取ってください。
```

これらのファイルは自由に編集して、用途に応じたプロンプトをカスタマイズできます。

## スクリプト

### test.py

Lambda関数を直接呼び出して、YOLO前処理 + Bedrock LLM解析を実行します。

#### 使用方法

```bash
python test.py <画像パス> \
  [--function-name pressure-gauge-detection] \
  [--user-prompt ./user_prompt.txt] \
  [--system-prompt ./system_prompt.txt] \
  [--no-preprocess] \
  [--output-dir ./output] \
  [--region us-east-1]
```

#### 実行例

```bash
# 仮想環境を有効化（まだの場合）
source venv/bin/activate  # macOS/Linux
# または venv\Scripts\activate  # Windows

# sample_images/0001.pngをテスト（デフォルトのプロンプトファイルを使用）
python test.py ../sample_images/0001.png

# カスタムプロンプトファイルを指定
python test.py ../sample_images/0002.png \
  --user-prompt ./my_user_prompt.txt \
  --system-prompt ./my_system_prompt.txt

# YOLO前処理をスキップ（オリジナル画像をそのままLLMに送信）
python test.py ../sample_images/0003.png --no-preprocess

# 別のLambda関数名を指定
python test.py ../sample_images/0004.png \
  --function-name my-custom-function
```

#### 引数

| 引数 | 必須 | デフォルト | 説明 |
|------|------|-----------|------|
| `image_path` | ✓ | - | テスト対象の画像ファイルパス |
| `--function-name` | | pressure-gauge-detection | Lambda関数名 |
| `--user-prompt` | | ./user_prompt.txt | ユーザープロンプトファイル |
| `--system-prompt` | | ./system_prompt.txt | システムプロンプトファイル |
| `--no-preprocess` | | False | 画像の前処理をスキップする |
| `--output-dir` | | ./output | 出力ディレクトリ |
| `--region` | | us-east-1 | AWSリージョン |

#### 出力

1. **YOLO処理結果**: 針の検出状況（例: "処理成功"）
2. **LLM解析結果**: Claude Sonnet 4.5による圧力値の読み取り結果
3. **前処理済み画像**: `output/<元ファイル名>_processed.png` に保存
   - 圧力計の針が赤色でハイライトされた画像
   - 針の先端に赤色の三角形マーカー

#### 出力例

```
================================================================================
圧力計メーター読み取りシステム 動作確認スクリプト
================================================================================
[INFO] 入力画像: ../sample_images/0001.png
[INFO] 出力ディレクトリ: output

[INFO] 画像を読み込み中...
[INFO] 読み込み完了（base64サイズ: 520644 characters）

[INFO] Lambda関数を呼び出し中...
[INFO] Function Name: pressure-gauge-detection
[INFO] Region: us-east-1

================================================================================
実行結果
================================================================================

[YOLO処理] 処理成功

[LLM解析結果]
--------------------------------------------------------------------------------
この圧力計の針は **約0.05 MPa** を指しています。

針は0と0.2の間の、0に近い位置を示しており、目盛りから判断すると
**0.05 MPa前後** の値を示していると読み取れます。
--------------------------------------------------------------------------------

[INFO] 前処理済み画像を保存中: output/0001_processed.png
[INFO] 保存完了

================================================================================
[SUCCESS] テストが完了しました
================================================================================
```

## 出力ディレクトリ

テスト実行時に生成される画像は `output/` ディレクトリに保存されます:

```
scripts/
├── output/
│   ├── 0001_processed.png      # 前処理済み画像
│   ├── 0002_processed.png
│   └── ...
├── test.py
├── requirements.txt
└── README.md
```

## トラブルシューティング

### 認証エラー

```
[ERROR] Lambda呼び出しエラー: An error occurred (ExpiredTokenException)
```

**解決方法**: AWS認証情報を確認してください
```bash
aws sts get-caller-identity
```

### Lambda関数が見つからない

```
[ERROR] Lambda呼び出しエラー: An error occurred (ResourceNotFoundException)
```

**解決方法**: Lambda関数がデプロイされているか確認してください
```bash
aws lambda get-function --function-name pressure-gauge-detection --region us-east-1
```

### Bedrock Model Accessエラー

```
[ERROR] Lambda function error: AccessDeniedException ... bedrock:InvokeModel
```

**解決方法**:
1. AWS Console → Amazon Bedrock → Model access (us-east-1リージョン)
2. Claude Sonnet 4.5 (`anthropic.claude-sonnet-4-5-20250929-v1:0`) のアクセスを有効化
3. 数分待ってから再試行

### 画像ファイルが見つからない

```
[ERROR] 画像ファイルが見つかりません: ../sample_images/0001.png
```

**解決方法**: 画像パスを確認してください
```bash
ls -la ../sample_images/
```

### リージョン関連のエラー

```
[ERROR] AccessDeniedException ... arn:aws:bedrock:us-east-2
```

**解決方法**: すべてus-east-1に統一されているか確認
- Lambda関数: us-east-1にデプロイされているか
- Bedrock Model Access: us-east-1で有効化されているか
- 環境変数: `BEDROCK_REGION=us-east-1` がLambda関数に設定されているか

## 技術仕様

### Lambda関数

- **リージョン**: us-east-1
- **メモリ**: 3GB
- **タイムアウト**: 120秒
- **環境変数**:
  - `MODEL_PATH`: `/opt/ml/model/best.pt`
  - `BEDROCK_REGION`: `us-east-1`
  - `CONF_THRESHOLD`: `0.65`
  - `IOU_THRESHOLD`: `0.5`

### Bedrockモデル

- **モデル**: Claude Sonnet 4.5
- **モデルID**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (inference profile)
- **リージョン**: us-east-1
- **入力**: 前処理済み画像（base64） + テキストプロンプト
- **出力**: 圧力値の読み取り結果

### YOLO処理

- **モデル**: YOLOv8 セグメンテーション
- **モード**: triangle（赤色針 + 赤色三角形マーカー）
- **検出対象**: 圧力計の針（POINTER）

## 参考情報

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [YOLOv8 Documentation](https://docs.ultralytics.com/)
