"""
AWS Lambda関数ハンドラー（Bedrock直接呼び出し版）
圧力計メーター針セグメンテーション処理 + Bedrock LLM解析
"""
import json
import base64
import os
import sys
from io import BytesIO
from typing import Dict, Any, List

import boto3
import cv2
import numpy as np
from PIL import Image

from yolo_processor import YOLOProcessor


# グローバル変数（コールドスタート対策）
processor = None
bedrock_client = None


def initialize_processor() -> YOLOProcessor:
    """
    YOLOプロセッサーを初期化（初回のみ実行）

    Returns:
        YOLOProcessor インスタンス
    """
    global processor

    if processor is None:
        # 環境変数から設定を取得
        model_path = os.environ.get("MODEL_PATH", "/opt/ml/model/best.pt")
        conf_threshold = float(os.environ.get("CONF_THRESHOLD", "0.65"))
        iou_threshold = float(os.environ.get("IOU_THRESHOLD", "0.5"))

        print(f"Initializing YOLO processor with model: {model_path}")

        processor = YOLOProcessor(
            model_path=model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
        )

        # モデルをロード
        processor.load_model()
        print("YOLO model loaded successfully")

    return processor


def initialize_bedrock_client():
    """
    Bedrock Runtimeクライアントを初期化（初回のみ実行）

    Returns:
        Bedrock Runtime クライアント
    """
    global bedrock_client

    if bedrock_client is None:
        region = os.environ.get("BEDROCK_REGION", "us-east-1")
        print(f"Initializing Bedrock Runtime client in region: {region}")
        bedrock_client = boto3.client("bedrock-runtime", region_name=region)
        print("Bedrock Runtime client initialized successfully")

    return bedrock_client


def decode_base64_image(base64_string: str) -> np.ndarray:
    """
    Base64文字列を画像(numpy配列)にデコード

    Args:
        base64_string: Base64エンコードされた画像文字列

    Returns:
        OpenCV形式の画像 (BGR, numpy.ndarray)
    """
    # Base64デコード
    image_bytes = base64.b64decode(base64_string)

    # PILで画像を開く
    image_pil = Image.open(BytesIO(image_bytes))

    # RGB -> BGR変換（OpenCV形式）
    image_rgb = np.array(image_pil)
    if len(image_rgb.shape) == 2:  # グレースケール
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_GRAY2BGR)
    elif image_rgb.shape[2] == 4:  # RGBA
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGBA2BGR)
    else:  # RGB
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

    return image_bgr


def encode_image_to_base64(image: np.ndarray, format: str = "PNG") -> str:
    """
    画像(numpy配列)をBase64文字列にエンコード

    Args:
        image: OpenCV形式の画像 (BGR, numpy.ndarray)
        format: 出力フォーマット ("PNG" or "JPEG")

    Returns:
        Base64エンコードされた画像文字列
    """
    # BGR -> RGB変換
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # PIL Imageに変換
    image_pil = Image.fromarray(image_rgb)

    # バイトストリームに書き込み
    buffer = BytesIO()
    image_pil.save(buffer, format=format)
    buffer.seek(0)

    # Base64エンコード
    image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

    return image_base64


def invoke_bedrock_model(
    client,
    processed_image_base64: str,
    user_prompt: str,
    system_prompt: str = None,
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
) -> str:
    """
    Bedrock LLMを呼び出して画像を解析

    Args:
        client: Bedrock Runtimeクライアント
        processed_image_base64: 前処理済み画像のBase64文字列
        user_prompt: ユーザープロンプト
        system_prompt: システムプロンプト（オプション）
        model_id: 使用するモデルID

    Returns:
        LLMからのレスポンステキスト
    """
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
                        "text": user_prompt
                    }
                ]
            }
        ]
    }

    # システムプロンプトが指定されている場合は追加
    if system_prompt:
        request_body["system"] = system_prompt

    print(f"Calling Bedrock model: {model_id}")
    print(f"System prompt: {system_prompt[:50] if system_prompt else 'None'}...")
    print(f"User prompt: {user_prompt[:50]}...")

    # Bedrock APIを呼び出し
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body)
    )

    # レスポンスを解析
    response_body = json.loads(response["body"].read())
    llm_response = response_body["content"][0]["text"]

    print(f"LLM response received: {llm_response[:100]}...")

    return llm_response


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数ハンドラー（Bedrock直接呼び出し版）

    Args:
        event: Lambdaイベント
            {
                "image": "base64エンコードされた画像",
                "userPrompt": "ユーザープロンプト",
                "systemPrompt": "システムプロンプト（オプション）",
                "preprocessImage": true/false（オプション、デフォルト: true）
            }
        context: Lambda実行コンテキスト

    Returns:
        {
            "statusCode": 200,
            "body": {
                "llmResponse": "LLMからの回答テキスト",
                "processedImage": "base64エンコードされた前処理済み画像",
                "yoloMessage": "YOLO処理結果メッセージ"
            }
        }
    """
    try:
        print("Lambda function started")
        print(f"Event keys: {event.keys()}")

        # プロセッサーとBedrockクライアントを初期化（初回のみ）
        bedrock = initialize_bedrock_client()

        # 入力パラメータを取得
        if "image" not in event:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "入力パラメータ 'image' が必要です"
                })
            }

        if "userPrompt" not in event:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "入力パラメータ 'userPrompt' が必要です"
                })
            }

        image_base64 = event["image"]
        user_prompt = event["userPrompt"]
        system_prompt = event.get("systemPrompt")  # オプション
        preprocess_image = event.get("preprocessImage", True)  # オプション、デフォルト: True

        print(f"Preprocess image: {preprocess_image}")

        # Base64デコード
        print("Decoding base64 image...")
        image = decode_base64_image(image_base64)
        print(f"Image shape: {image.shape}")

        # 前処理の有無を判定
        if preprocess_image:
            # プロセッサーを初期化（前処理する場合のみ）
            proc = initialize_processor()

            # YOLO画像処理（triangle固定）
            print("Processing image with YOLO...")
            processed_image, yolo_message = proc.process_image(image)
            print(f"YOLO processing result: {yolo_message}")

            # 前処理済み画像をBase64エンコード
            print("Encoding processed image to base64...")
            processed_image_base64 = encode_image_to_base64(processed_image)
        else:
            # 前処理をスキップ
            print("Skipping YOLO preprocessing...")
            processed_image = image
            yolo_message = "前処理をスキップしました"

            # オリジナル画像をBase64エンコード
            print("Encoding original image to base64...")
            processed_image_base64 = encode_image_to_base64(processed_image)

        # Bedrock LLMを呼び出し
        print("Invoking Bedrock LLM...")
        llm_response = invoke_bedrock_model(
            client=bedrock,
            processed_image_base64=processed_image_base64,
            user_prompt=user_prompt,
            system_prompt=system_prompt
        )

        # レスポンスを返す
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "llmResponse": llm_response,
                "processedImage": processed_image_base64,
                "yoloMessage": yolo_message
            })
        }

        print("Lambda function completed successfully")
        return response

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "type": type(e).__name__
            })
        }
