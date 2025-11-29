# AWS Lambda用Dockerイメージ
# Python 3.11ベース

FROM public.ecr.aws/lambda/python:3.11

# 作業ディレクトリ
WORKDIR /var/task

# システムパッケージの更新とOpenCV依存関係のインストール
# ビルドツールも追加（matplotlib等のビルドに必要）
RUN yum update -y && \
    yum install -y \
    gcc \
    gcc-c++ \
    mesa-libGL \
    glib2 \
    libgomp \
    && yum clean all

# pipをアップグレード
RUN pip install --upgrade pip

# requirements.txtをコピー
COPY requirements.txt .

# NumPyを先にインストール（ビルド済みバイナリを使用）
RUN pip install --no-cache-dir "numpy>=1.24.0,<2.0.0"

# PyTorchとその他の依存パッケージをインストール
# CPU版PyTorchを使用（Lambda環境にGPUは不要）
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu

# その他の依存パッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY lambda_function.py .
COPY yolo_processor.py .

# モデルファイルをコピー
RUN mkdir -p /opt/ml/model
COPY best.pt /opt/ml/model/best.pt

# 環境変数の設定
ENV MODEL_PATH=/opt/ml/model/best.pt
ENV CONF_THRESHOLD=0.65
ENV IOU_THRESHOLD=0.5

# Lambda関数ハンドラーを指定
CMD ["lambda_function.lambda_handler"]
