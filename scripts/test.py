#!/usr/bin/env python3
"""
圧力計メーター読み取りシステム動作確認スクリプト

Lambda関数を呼び出して、YOLO前処理 + Bedrock LLM解析を実行します。
"""
import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError


def load_image_as_base64(image_path: Path) -> str:
    """
    画像ファイルをbase64エンコードして返す

    Args:
        image_path: 画像ファイルパス

    Returns:
        base64エンコードされた画像文字列
    """
    with open(image_path, 'rb') as f:
        image_data = f.read()
    return base64.b64encode(image_data).decode('utf-8')


def save_base64_image(base64_string: str, output_path: Path) -> None:
    """
    base64文字列を画像ファイルとして保存

    Args:
        base64_string: base64エンコードされた画像文字列
        output_path: 保存先パス
    """
    image_data = base64.b64decode(base64_string)
    with open(output_path, 'wb') as f:
        f.write(image_data)


def load_prompt_file(prompt_path: Path) -> str:
    """
    プロンプトファイルを読み込む

    Args:
        prompt_path: プロンプトファイルパス

    Returns:
        プロンプトテキスト
    """
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def invoke_lambda_function(
    function_name: str,
    image_base64: str,
    user_prompt: str,
    system_prompt: str,
    preprocess_image: bool = True,
    region: str = 'us-east-1'
) -> Dict[str, Any]:
    """
    Lambda関数を呼び出して画像を解析

    Args:
        function_name: Lambda関数名
        image_base64: base64エンコードされた画像
        user_prompt: ユーザープロンプト
        system_prompt: システムプロンプト
        preprocess_image: 画像を前処理するかどうか（デフォルト: True）
        region: AWSリージョン

    Returns:
        Lambda関数からのレスポンス
    """
    client = boto3.client('lambda', region_name=region)

    print(f"[INFO] Lambda関数を呼び出し中...")
    print(f"[INFO] Function Name: {function_name}")
    print(f"[INFO] Region: {region}")
    print(f"[INFO] Preprocess Image: {preprocess_image}")
    print(f"[INFO] System Prompt: {system_prompt[:50]}..." if len(system_prompt) > 50 else f"[INFO] System Prompt: {system_prompt}")
    print(f"[INFO] User Prompt: {user_prompt[:50]}..." if len(user_prompt) > 50 else f"[INFO] User Prompt: {user_prompt}")
    print(f"[INFO] Image Size: {len(image_base64)} characters (base64)")
    print()

    # Lambda呼び出しペイロードを構築
    payload = {
        'image': image_base64,
        'userPrompt': user_prompt,
        'systemPrompt': system_prompt,
        'preprocessImage': preprocess_image
    }

    try:
        # Lambda関数を呼び出し
        response = client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        # レスポンスを解析
        response_payload = json.loads(response['Payload'].read())

        # エラーチェック
        if response_payload.get('statusCode') != 200:
            error_body = json.loads(response_payload.get('body', '{}'))
            raise Exception(f"Lambda function error: {error_body}")

        # ボディをパース
        body = json.loads(response_payload['body'])

        return {
            'llm_response': body['llmResponse'],
            'processed_image': body['processedImage'],
            'yolo_message': body['yoloMessage']
        }

    except ClientError as e:
        print(f"[ERROR] Lambda呼び出しエラー: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"[ERROR] 処理エラー: {e}", file=sys.stderr)
        raise


def main() -> int:
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='圧力計メーター読み取りシステム動作確認スクリプト'
    )
    parser.add_argument(
        'image_path',
        type=Path,
        help='テスト対象の画像ファイルパス（例: ../sample_images/0001.png）'
    )
    parser.add_argument(
        '--function-name',
        type=str,
        default='pressure-gauge-detection',
        help='Lambda関数名（デフォルト: pressure-gauge-detection）'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path(__file__).parent / 'output',
        help='出力ディレクトリ（デフォルト: ./output）'
    )
    parser.add_argument(
        '--region',
        type=str,
        default='us-east-1',
        help='AWSリージョン（デフォルト: us-east-1）'
    )
    parser.add_argument(
        '--user-prompt',
        type=Path,
        default=Path(__file__).parent / 'user_prompt.txt',
        help='ユーザープロンプトファイル（デフォルト: ./user_prompt.txt）'
    )
    parser.add_argument(
        '--system-prompt',
        type=Path,
        default=Path(__file__).parent / 'system_prompt.txt',
        help='システムプロンプトファイル（デフォルト: ./system_prompt.txt）'
    )
    parser.add_argument(
        '--no-preprocess',
        action='store_true',
        help='画像の前処理をスキップする（デフォルト: 前処理あり）'
    )

    args = parser.parse_args()

    # 画像ファイルの存在確認
    if not args.image_path.exists():
        print(f"[ERROR] 画像ファイルが見つかりません: {args.image_path}", file=sys.stderr)
        return 1

    # プロンプトファイルの存在確認
    if not args.user_prompt.exists():
        print(f"[ERROR] ユーザープロンプトファイルが見つかりません: {args.user_prompt}", file=sys.stderr)
        return 1

    if not args.system_prompt.exists():
        print(f"[ERROR] システムプロンプトファイルが見つかりません: {args.system_prompt}", file=sys.stderr)
        return 1

    # 出力ディレクトリの作成
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("圧力計メーター読み取りシステム 動作確認スクリプト")
    print("=" * 80)
    print(f"[INFO] 入力画像: {args.image_path}")
    print(f"[INFO] ユーザープロンプト: {args.user_prompt}")
    print(f"[INFO] システムプロンプト: {args.system_prompt}")
    print(f"[INFO] 画像前処理: {'スキップ' if args.no_preprocess else '実行'}")
    print(f"[INFO] 出力ディレクトリ: {args.output_dir}")
    print()

    try:
        # 画像を読み込み
        print("[INFO] 画像を読み込み中...")
        image_base64 = load_image_as_base64(args.image_path)
        print(f"[INFO] 読み込み完了（base64サイズ: {len(image_base64)} characters）")
        print()

        # プロンプトファイルを読み込み
        print("[INFO] プロンプトファイルを読み込み中...")
        user_prompt = load_prompt_file(args.user_prompt)
        system_prompt = load_prompt_file(args.system_prompt)
        print(f"[INFO] ユーザープロンプト読み込み完了（{len(user_prompt)} characters）")
        print(f"[INFO] システムプロンプト読み込み完了（{len(system_prompt)} characters）")
        print()

        # Lambda関数を呼び出し
        result = invoke_lambda_function(
            function_name=args.function_name,
            image_base64=image_base64,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            preprocess_image=not args.no_preprocess,  # --no-preprocessが指定されていない場合はTrue
            region=args.region
        )

        print()
        print("=" * 80)
        print("実行結果")
        print("=" * 80)
        print()

        # YOLO処理結果
        print(f"[YOLO処理] {result['yolo_message']}")
        print()

        # LLMレスポンス
        print("[LLM解析結果]")
        print("-" * 80)
        print(result['llm_response'])
        print("-" * 80)
        print()

        # 前処理済み画像を保存
        output_filename = args.image_path.stem + '_processed.png'
        output_path = args.output_dir / output_filename
        print(f"[INFO] 前処理済み画像を保存中: {output_path}")
        save_base64_image(result['processed_image'], output_path)
        print(f"[INFO] 保存完了")
        print()

        print("=" * 80)
        print("[SUCCESS] テストが完了しました")
        print("=" * 80)
        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"[ERROR] エラーが発生しました: {e}", file=sys.stderr)
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
