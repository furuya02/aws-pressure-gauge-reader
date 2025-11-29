# Pressure Gauge Detection with Bedrock Agent

圧力計メーター針をYOLOv8で検出し、Bedrock Agent (Claude Sonnet 4.5) でマルチモーダル解析を行うシステムのCDKプロジェクトです。

## アーキテクチャ

```
ユーザー
  ↓ 画像 + テキスト指示
Bedrock Agent (Claude Sonnet 4.5)
  ↓ detect-gaugeアクション呼び出し
Lambda関数（YOLO針検出）
  ↓ 針を強調した画像を返す
Bedrock Agent
  ↓ 強調画像をLLMに渡して解析
  ↓ メーター値を読み取り
ユーザーへ結果を返す
```

## 構成要素

- **Lambda関数**: YOLOv8による圧力計針のセグメンテーション（コンテナイメージ形式）
- **ECRリポジトリ**: Dockerイメージの保存
- **Bedrock Agent**: Claude Sonnet 4.5を使用した画像解析エージェント
- **IAMロール**: Lambda実行ロール、Bedrock Agent実行ロール
- **Action Group**: Lambda関数を呼び出すBedrock Agent Action

## 前提条件

1. **AWS CLI**がインストール・設定されていること
2. **Node.js 18以上**がインストールされていること
3. **Docker**がインストールされていること
4. **AWS CDK**がインストールされていること
5. **Bedrock Model Access**でClaude Sonnet 4.5へのアクセスが有効化されていること（us-east-1）

## セットアップ

### 1. 依存パッケージのインストール

\`\`\`bash
cd cdk
pnpm install
\`\`\`

### 2. AWS認証情報の設定

\`\`\`bash
aws configure
# または環境変数を設定
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
\`\`\`

### 3. CDKのブートストラップ（初回のみ）

\`\`\`bash
pnpm exec cdk bootstrap aws://ACCOUNT-ID/us-east-1
\`\`\`

## デプロイ

### 1. CDK Synthで検証

\`\`\`bash
pnpm exec cdk synth
\`\`\`

### 2. デプロイ実行

\`\`\`bash
pnpm exec cdk deploy
\`\`\`

**注意**: 初回デプロイ時は、Dockerイメージのビルドに時間がかかります（10-20分程度）。

デプロイが完了すると、以下の情報が出力されます:
- \`ECRRepositoryUri\`: ECRリポジトリのURI
- \`LambdaFunctionName\`: Lambda関数名
- \`LambdaFunctionArn\`: Lambda関数のARN
- \`BedrockAgentId\`: Bedrock AgentのID
- \`BedrockAgentArn\`: Bedrock AgentのARN
- \`BedrockAgentAliasId\`: Bedrock Agent AliasのID

## 使用方法

### AWS Console経由

1. AWS Consoleで **Amazon Bedrock** サービスを開く
2. 左メニューから **Agents** を選択
3. \`pressure-gauge-agent\` を選択
4. **Test** タブを開く
5. 圧力計の画像をアップロードして、「この圧力計のメーターを読み取ってください」と入力
6. Agentが画像を解析して結果を返す

### AWS CLI経由

\`\`\`bash
aws bedrock-agent-runtime invoke-agent \\
  --agent-id <AGENT_ID> \\
  --agent-alias-id <ALIAS_ID> \\
  --session-id test-session-1 \\
  --input-text "この圧力計のメーターを読み取ってください" \\
  --region us-east-1 \\
  output.json
\`\`\`

## デプロイ後の設定

### Bedrock Model Accessの有効化

1. AWS Console → Amazon Bedrock → Model access
2. Claude Sonnet 4.5 (anthropic.claude-sonnet-4-20250514-v1:0) を選択
3. **Request access** をクリック
4. 承認されるまで待機（通常は即座に承認される）

## トラブルシューティング

### デプロイエラー: Bedrock Model Accessがない

\`\`\`
Error: Model access not granted for anthropic.claude-sonnet-4-20250514-v1:0
\`\`\`

**解決方法:**
上記の「Bedrock Model Accessの有効化」を実施してください。

### Dockerビルドエラー

\`\`\`
Error: Docker build failed
\`\`\`

**解決方法:**
1. Dockerが起動していることを確認
2. \`lambda/best.pt\`が存在することを確認（約6.7MB）
3. ディスク容量を確認

## クリーンアップ

すべてのリソースを削除する場合:

\`\`\`bash
pnpm exec cdk destroy
\`\`\`

**注意**: ECRリポジトリ内の画像も自動削除されます（\`autoDeleteImages: true\`設定のため）。

## コスト

主なコスト要素:
- **Lambda実行**: メモリ3GB × 実行時間
- **ECRストレージ**: Dockerイメージサイズ（約1.5GB）
- **Bedrock Agent**: Claude Sonnet 4.5の使用量（入力・出力トークン数）

## ライセンス

元のプログラムのライセンスに準拠します。
