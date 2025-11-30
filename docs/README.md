# 技術ドキュメント

このディレクトリには、AWS Pressure Gauge Readerプロジェクトの詳細な技術ドキュメントが格納されています。

## ドキュメント構成

```
docs/
├── 00_overview/                    # プロジェクト概要
├── 01_architecture/                # アーキテクチャ設計
│   ├── 01_why-not-bedrock-agent.md
│   └── 02_bedrock-agent-image-limitation.md
└── 02_implementation/              # 実装ガイド
    ├── 01_lambda-ml-implementation-guide.md
    └── 02_claude-sonnet-4.5-on-cdk.md
```

## 00_overview - プロジェクト概要

現在、このディレクトリにドキュメントはありません。プロジェクト全体の概要は [../CLAUDE.md](../CLAUDE.md) および [../README.md](../README.md) を参照してください。

## 01_architecture - アーキテクチャ設計

### [01_why-not-bedrock-agent.md](01_architecture/01_why-not-bedrock-agent.md)
Bedrock Agentを使用せず、Lambda関数から直接Bedrock LLMを呼び出すアーキテクチャを選択した理由を詳しく解説します。

**主なトピック:**
- Bedrock Agentを試行した経緯
- sessionState.filesの制約
- 単一アクションでの非効率性
- Lambda直接呼び出しのメリット・デメリット
- アーキテクチャの比較と推奨される使い分け

### [02_bedrock-agent-image-limitation.md](01_architecture/02_bedrock-agent-image-limitation.md)
Bedrock Agentで画像データをAction Groupに連携できない理由について、詳細な試行錯誤の記録です。

**主なトピック:**
- sessionState.filesの設計目的
- Code Interpreter機能との関係
- promptOverrideConfigurationとの競合
- 技術的な制約の詳細分析
- 代替ソリューション（S3統合方式など）

## 02_implementation - 実装ガイド

### [01_lambda-ml-implementation-guide.md](02_implementation/01_lambda-ml-implementation-guide.md)
AWS Lambdaで機械学習モデル（YOLOv8）を実装する際のベストプラクティスとトラブルシューティングガイドです。

**主なトピック:**
- Lambda Layer vs Dockerコンテナイメージの比較
- Dockerfileの実装詳細
- Lambda制限事項（メモリ、タイムアウト、ペイロードサイズ）
- コールドスタート対策（グローバル変数キャッシング）
- パフォーマンス最適化
- よくあるエラーと解決方法

### [02_claude-sonnet-4.5-on-cdk.md](02_implementation/02_claude-sonnet-4.5-on-cdk.md)
AWS CDKでClaude Sonnet 4.5を利用する際の制約と実装方法を詳しく解説します。

**主なトピック:**
- AWS CDKバージョンの制約（2.220.0時点）
- Inference Profile IDとFoundation Model IDの違い
- IAMポリシー設定（ワイルドカード許可の必要性）
- リージョン設定の重要性
- Model Accessの有効化手順
- よくある問題と解決策

## ドキュメントの使い方

### 初めて開発に参加する場合

1. [../CLAUDE.md](../CLAUDE.md) - プロジェクト全体の概要を把握
2. [../README.md](../README.md) - セットアップ手順を実施
3. [01_architecture/01_why-not-bedrock-agent.md](01_architecture/01_why-not-bedrock-agent.md) - アーキテクチャの設計思想を理解
4. [02_implementation/01_lambda-ml-implementation-guide.md](02_implementation/01_lambda-ml-implementation-guide.md) - 実装の詳細を確認

### トラブルシューティングの場合

- Lambda関連のエラー → [02_implementation/01_lambda-ml-implementation-guide.md](02_implementation/01_lambda-ml-implementation-guide.md)
- Bedrock/Claude Sonnet 4.5のエラー → [02_implementation/02_claude-sonnet-4.5-on-cdk.md](02_implementation/02_claude-sonnet-4.5-on-cdk.md)
- Bedrock Agent関連の調査 → [01_architecture/02_bedrock-agent-image-limitation.md](01_architecture/02_bedrock-agent-image-limitation.md)

### アーキテクチャ変更を検討する場合

- [01_architecture/01_why-not-bedrock-agent.md](01_architecture/01_why-not-bedrock-agent.md) - 現在のアーキテクチャ選択の背景を理解
- [01_architecture/02_bedrock-agent-image-limitation.md](01_architecture/02_bedrock-agent-image-limitation.md) - Bedrock Agentの技術的制約を確認

## 関連リンク

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
