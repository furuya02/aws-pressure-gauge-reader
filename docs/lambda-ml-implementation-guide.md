# AWS Lambdaでの機械学習モデル実装ガイド

## 目次

1. [概要](#概要)
2. [デプロイ方式の比較](#デプロイ方式の比較)
3. [本プロジェクトでの選択](#本プロジェクトでの選択)
4. [Lambda制限事項](#lambda制限事項)
5. [実装上の留意点](#実装上の留意点)
6. [コールドスタート対策](#コールドスタート対策)
7. [トラブルシューティング](#トラブルシューティング)

## 概要

AWS Lambdaで機械学習モデル（特にYOLOv8などの大規模モデル）を実装する際には、Lambdaの制限事項を理解し、適切なデプロイ方式を選択する必要があります。

本ドキュメントでは、圧力計メーター読み取りプロジェクトでの実装経験に基づき、Lambda上で機械学習モデルを動かす際の留意点を詳しく解説します。

## デプロイ方式の比較

### 1. Lambda Layer方式

Lambda Layerは、共通ライブラリや依存関係をパッケージ化して複数のLambda関数で共有する仕組みです。

#### メリット
- ✅ 関数コードとライブラリを分離できる
- ✅ 複数の関数で同じLayerを再利用可能
- ✅ デプロイパッケージサイズを削減できる
- ✅ セットアップが比較的シンプル

#### デメリット
- ❌ **サイズ制限**: Layer + 関数コードの合計が250MB（解凍後）に制限される
- ❌ **依存関係の複雑さ**: numpy, OpenCV, PyTorch, YOLOなどを含めると250MBを大幅に超過
- ❌ **バージョン管理の煩雑さ**: Layer更新時に全関数の再デプロイが必要な場合がある
- ❌ **ネイティブライブラリ**: OpenCV-pythonなどはコンパイル済みバイナリが必要で扱いにくい

#### 実際のサイズ例
```
torch (CPU版):        ~130MB
torchvision:          ~20MB
opencv-python:        ~30MB
ultralytics (YOLO):   ~10MB
numpy:                ~20MB
pillow:               ~10MB
--------------------------------
合計:                 ~220MB

モデルファイル(best.pt): ~7MB
--------------------------------
総計:                 ~227MB
```

一見250MB以内に収まりそうですが、実際には：
- 依存関係の依存関係（transitive dependencies）が追加される
- C拡張モジュールのバイナリサイズが大きい
- 解凍後のサイズで制限がかかる

### 2. Dockerコンテナイメージ方式

Dockerコンテナイメージをビルドし、ECRにプッシュしてLambdaで実行する方式です。

#### メリット
- ✅ **大容量対応**: イメージサイズは**10GB**まで対応
- ✅ **柔軟性**: 任意のベースイメージやシステムパッケージを使用可能
- ✅ **再現性**: ローカルで完全に同じ環境でテスト可能
- ✅ **依存関係管理**: Dockerfileで明示的に管理
- ✅ **ネイティブライブラリ**: yum/aptで簡単にインストール可能

#### デメリット
- ❌ ECRの管理が必要
- ❌ ビルド時間が長い（初回）
- ❌ デプロイサイズが大きいとコールドスタートが遅くなる可能性

#### 実際のサイズ例（本プロジェクト）
```
ベースイメージ (public.ecr.aws/lambda/python:3.11):  ~500MB
PyTorch (CPU版):                                      ~130MB
OpenCV + 依存パッケージ:                              ~50MB
Ultralytics (YOLO):                                   ~15MB
その他Pythonライブラリ:                               ~30MB
モデルファイル (best.pt):                             ~7MB
----------------------------------------------------------------
合計:                                                 ~732MB
```

10GBの制限に対して余裕があり、将来的なモデルの大型化にも対応可能です。

## 本プロジェクトでの選択

### 選択: Dockerコンテナイメージ方式

**理由:**

1. **サイズ制限の回避**
   - YOLOv8 + PyTorch + OpenCVの組み合わせはLayer方式の250MB制限を超過
   - Dockerなら10GBまで対応可能

2. **開発効率**
   - ローカルでDockerコンテナとして動作確認可能
   - `docker run`でLambdaと同じ環境を再現できる

3. **デプロイの簡素化**
   - モデルファイルをイメージに含めることで、Layerの管理が不要
   - 単一のイメージで完結

4. **将来の拡張性**
   - より大きなモデルへの移行が容易
   - 追加のライブラリ導入が柔軟

### ディレクトリ構成

```
cdk/lambda/
├── Dockerfile              # Lambda用コンテナイメージ定義
├── requirements.txt        # Python依存パッケージ
├── lambda_function.py      # Lambda関数ハンドラー
├── yolo_processor.py       # YOLO処理ロジック
└── best.pt                 # YOLOv8モデルファイル (6.7MB)
```

### Dockerfile

```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# 作業ディレクトリ
WORKDIR /var/task

# システムパッケージのインストール（OpenCV依存）
RUN yum update -y && \
    yum install -y \
    gcc \
    gcc-c++ \
    mesa-libGL \
    glib2 \
    libgomp \
    && yum clean all

# pipのアップグレード
RUN pip install --upgrade pip

# requirements.txtをコピー
COPY requirements.txt .

# numpyを先にインストール（バージョン固定）
RUN pip install --no-cache-dir "numpy>=1.24.0,<2.0.0"

# PyTorchをCPU版でインストール
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu

# その他のPythonパッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# Lambda関数コードをコピー
COPY lambda_function.py .
COPY yolo_processor.py .

# モデルファイル用ディレクトリを作成
RUN mkdir -p /opt/ml/model

# モデルファイルをコピー
COPY best.pt /opt/ml/model/best.pt

# Lambda関数ハンドラーを指定
CMD ["lambda_function.lambda_handler"]
```

**重要なポイント:**

1. **ベースイメージ**: `public.ecr.aws/lambda/python:3.11`
   - AWSが提供するLambda公式イメージ
   - Lambda Runtime APIが組み込み済み

2. **システムパッケージ**: OpenCV依存パッケージを`yum`でインストール
   - `mesa-libGL`: OpenCVのGUI機能用
   - `glib2`: OpenCVの依存ライブラリ
   - `libgomp`: OpenMPサポート

3. **PyTorch CPU版**: `--extra-index-url`でCPU専用版を指定
   - GPU版より約1GB小さい
   - Lambda環境にはGPUがないためCPU版で十分

4. **numpy バージョン固定**: `>=1.24.0,<2.0.0`
   - numpy 2.0はまだ一部ライブラリと互換性問題あり

5. **モデルファイル配置**: `/opt/ml/model/best.pt`
   - 環境変数`MODEL_PATH`で参照

## Lambda制限事項

### リソース制限

| リソース | 制限値 | 本プロジェクト設定 | 備考 |
|---------|--------|------------------|------|
| メモリ | 128MB ~ 10,240MB (10GB) | **3,008MB (3GB)** | YOLOv8推論に必要 |
| タイムアウト | 最大900秒 (15分) | **120秒** | 通常2-5秒で完了 |
| /tmp ストレージ | 512MB ~ 10,240MB | デフォルト (512MB) | 使用していない |
| デプロイパッケージサイズ | 250MB (解凍後、Layer方式) | - | Docker方式では無関係 |
| コンテナイメージサイズ | 10GB | **732MB** | 余裕あり |
| 同時実行数 | アカウント毎にデフォルト1,000 | 制限なし設定 | 必要に応じて引き上げ可能 |

### 実行環境

- **CPU**: x86_64アーキテクチャ、2vCPU相当（3GB設定時）
- **GPU**: 利用不可
- **ネットワーク**: アウトバウンド接続可能（インターネット、VPC内リソース）

### ペイロードサイズ制限

| 呼び出し方式 | 制限値 | 本プロジェクト |
|------------|--------|--------------|
| 同期呼び出し (RequestResponse) | 6MB | **画像Base64が約520KB** ← OK |
| 非同期呼び出し (Event) | 256KB | 使用していない |

**注意点:**
- 入力画像をBase64エンコードすると約1.33倍になる
- 640x361ピクセルのPNG画像（約390KB）→ Base64で約520KB
- 大きな画像は事前にリサイズするか、S3経由で渡す必要がある

## 実装上の留意点

### 1. コールドスタート時間

Dockerコンテナイメージ方式では、コールドスタート時に以下の処理が発生します：

```
コールドスタート内訳（本プロジェクト実測）:
1. コンテナイメージのダウンロード:     ~2秒
2. コンテナの起動:                     ~1秒
3. Python環境の初期化:                 ~0.5秒
4. YOLOモデルのロード:                 ~1.5秒
----------------------------------------
合計:                                  ~5秒
```

**対策:**
- グローバル変数でモデルをキャッシュ（後述）
- Provisioned Concurrency（有料）の利用を検討
- Lambda SnapStart（Java専用、Pythonは非対応）

### 2. メモリ設定の最適化

メモリサイズによってCPU性能も比例して変化します：

| メモリ | vCPU | YOLOv8推論時間 | 月額コスト (1,000回/日) |
|-------|------|--------------|----------------------|
| 1,024MB | 0.6vCPU | ~8秒 | $8.33 |
| 2,048MB | 1.2vCPU | ~4秒 | $16.67 |
| **3,008MB** | **1.8vCPU** | **~2秒** | **$25.00** |
| 5,120MB | 3.0vCPU | ~1.5秒 | $42.67 |

**選択理由（3GB）:**
- YOLOv8モデルのメモリ使用量: 約400-500MB
- PyTorch + OpenCVのメモリ: 約200-300MB
- 推論時の一時メモリ: 約500MB
- バッファ: 約1.5-2GB

### 3. タイムアウト設定

```python
# CDKでの設定例
timeout: cdk.Duration.seconds(120)  # 120秒
```

**実測値:**
- 初回（コールドスタート）: 約5秒
- 2回目以降（ウォーム）: 約2秒
- Bedrock LLM呼び出し含む: 約3-10秒

**推奨値:** 120秒（余裕を持たせる）

### 4. 環境変数の活用

```python
# CDKでの環境変数設定
environment: {
  MODEL_PATH: '/opt/ml/model/best.pt',
  CONF_THRESHOLD: '0.65',
  IOU_THRESHOLD: '0.5',
  BEDROCK_REGION: 'us-east-1',
}
```

**メリット:**
- コードを変更せずに設定を変更可能
- 環境（dev/prod）ごとに異なる設定を適用可能

### 5. エラーハンドリング

```python
def lambda_handler(event, context):
    try:
        # 処理
        pass
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()  # CloudWatch Logsに詳細を出力

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "type": type(e).__name__
            })
        }
```

**重要:**
- `traceback.print_exc()`でCloudWatch Logsに詳細を出力
- エラータイプ（`type(e).__name__`）も返すと原因特定が容易

## コールドスタート対策

### グローバル変数によるモデルキャッシュ

Lambda関数は、同じコンテナインスタンスが再利用される場合、グローバル変数が保持されます。

```python
# グローバル変数（コールドスタート対策）
processor = None
bedrock_client = None


def initialize_processor() -> YOLOProcessor:
    """YOLOプロセッサーを初期化（初回のみ実行）"""
    global processor

    if processor is None:
        model_path = os.environ.get("MODEL_PATH", "/opt/ml/model/best.pt")
        print(f"Initializing YOLO processor with model: {model_path}")

        processor = YOLOProcessor(
            model_path=model_path,
            conf_threshold=float(os.environ.get("CONF_THRESHOLD", "0.65")),
            iou_threshold=float(os.environ.get("IOU_THRESHOLD", "0.5")),
        )
        processor.load_model()
        print("YOLO model loaded successfully")

    return processor


def lambda_handler(event, context):
    # 初回のみロード、2回目以降は再利用
    proc = initialize_processor()

    # 推論実行
    output_image, message = proc.process_image(image)
    ...
```

**効果:**
- 初回: モデルロード時間を含む（約5秒）
- 2回目以降: モデルロード不要（約2秒）
- **約60%の時間短縮**

### Provisioned Concurrency（有料オプション）

常に一定数のインスタンスを起動状態に保つ機能です。

```typescript
// CDKでの設定例
const version = gaugeDetectionFunction.currentVersion;
const alias = new lambda.Alias(this, 'live', {
  aliasName: 'live',
  version: version,
  provisionedConcurrentExecutions: 2,  // 2インスタンスを常時起動
});
```

**メリット:**
- コールドスタートがゼロ（常にウォーム状態）

**デメリット:**
- **コストが高い**: 24時間365日起動状態のため、月額約$20-30（1インスタンス）

**使用推奨シーン:**
- レイテンシが非常に重要な本番環境
- トラフィックの予測が可能な場合

## トラブルシューティング

### 問題1: メモリ不足エラー

```
Error: Runtime exited with error: signal: killed
```

**原因:** Lambda関数のメモリ設定が小さすぎる

**解決策:**
1. CloudWatch Logsでメモリ使用量を確認
2. メモリ設定を引き上げ（推奨: 3GB以上）

```typescript
memorySize: 3008,  // 3GB
```

### 問題2: タイムアウト

```
Task timed out after 30.00 seconds
```

**原因:** タイムアウト設定が短すぎる

**解決策:**
```typescript
timeout: cdk.Duration.seconds(120),  // 120秒
```

### 問題3: モデルファイルが見つからない

```
FileNotFoundError: [Errno 2] No such file or directory: '/opt/ml/model/best.pt'
```

**原因:**
- Dockerfileでモデルファイルがコピーされていない
- 環境変数`MODEL_PATH`が間違っている

**解決策:**
```dockerfile
# Dockerfileで確実にコピー
COPY best.pt /opt/ml/model/best.pt
```

```python
# Lambda関数で環境変数を確認
model_path = os.environ.get("MODEL_PATH", "/opt/ml/model/best.pt")
print(f"Model path: {model_path}")
print(f"File exists: {os.path.exists(model_path)}")
```

### 問題4: OpenCVエラー

```
ImportError: libGL.so.1: cannot open shared object file
```

**原因:** OpenCV依存のシステムライブラリが不足

**解決策:** Dockerfileにシステムパッケージを追加
```dockerfile
RUN yum install -y mesa-libGL glib2 libgomp
```

### 問題5: numpy互換性エラー

```
ValueError: numpy.dtype size changed, may indicate binary incompatibility
```

**原因:** numpy 2.0との互換性問題

**解決策:**
```dockerfile
# numpy 1.x系を指定
RUN pip install --no-cache-dir "numpy>=1.24.0,<2.0.0"
```

## まとめ

### Lambda Layer vs Dockerコンテナイメージ

| 観点 | Lambda Layer | Dockerコンテナイメージ |
|-----|-------------|---------------------|
| サイズ制限 | 250MB (解凍後) | 10GB |
| 機械学習モデル対応 | ❌ 厳しい | ✅ 十分 |
| セットアップ | シンプル | やや複雑 |
| ローカルテスト | 困難 | 容易 |
| 本番推奨 | 小規模モデル | **大規模モデル** |

### 推奨設定（YOLOv8 + Bedrock）

```typescript
{
  memorySize: 3008,                    // 3GB
  timeout: cdk.Duration.seconds(120),  // 120秒
  environment: {
    MODEL_PATH: '/opt/ml/model/best.pt',
    BEDROCK_REGION: 'us-east-1',
  },
}
```

### チェックリスト

- ✅ Dockerコンテナイメージ方式を選択
- ✅ メモリ3GB以上に設定
- ✅ タイムアウト120秒に設定
- ✅ グローバル変数でモデルキャッシュ
- ✅ CloudWatch Logsで実行時間・メモリ使用量を監視
- ✅ エラーハンドリングとログ出力を実装
- ✅ システムパッケージ（OpenCV依存）を含める
- ✅ numpy 1.x系を使用

これらのベストプラクティスに従うことで、Lambda上で安定した機械学習モデル推論環境を構築できます。
