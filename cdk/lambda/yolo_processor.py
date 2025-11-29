"""
YOLO圧力計針セグメンテーション処理モジュール
Lambda環境用にリファクタリング
"""
import cv2
import numpy as np
from ultralytics import YOLO
from typing import Tuple, Optional


class YOLOProcessor:
    """YOLO圧力計針セグメンテーション処理クラス"""

    def __init__(
        self,
        model_path: str = "/opt/ml/model/best.pt",
        conf_threshold: float = 0.65,
        iou_threshold: float = 0.5,
        color: Tuple[int, int, int] = (0, 0, 200),
    ):
        """
        初期化

        Args:
            model_path: YOLOモデルファイルパス
            conf_threshold: 信頼度閾値
            iou_threshold: IOU閾値
            color: オーバーレイ色 (BGR)
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.color = color
        self.model = None

    def load_model(self) -> None:
        """YOLOモデルをロード"""
        self.model = YOLO(self.model_path)

    def overlay(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        color: tuple,
        alpha: float,
        resize: tuple = None,
    ) -> np.ndarray:
        """マスクを画像に重ねる"""
        colored_mask = np.expand_dims(mask, 0).repeat(3, axis=0)
        colored_mask = np.moveaxis(colored_mask, 0, -1)
        masked = np.ma.MaskedArray(image, mask=colored_mask, fill_value=color)
        image_overlay = masked.filled()
        if resize is not None:
            image = cv2.resize(image.transpose(1, 2, 0), resize)
            image_overlay = cv2.resize(image_overlay.transpose(1, 2, 0), resize)
        image_combined = cv2.addWeighted(image, 1 - alpha, image_overlay, alpha, 0)
        return image_combined

    def detect_needle_tip(
        self, mask: np.ndarray, center_x: int, center_y: int
    ) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """
        中心から最も遠い点を先端とみなす

        Args:
            mask: 針のセグメンテーションマスク (0 or 1)
            center_x: ゲージ中心のx座標
            center_y: ゲージ中心のy座標

        Returns:
            (tip_x, tip_y, base_x, base_y): 先端座標と基部座標
        """
        # マスクから針の座標を取得
        needle_points = np.argwhere(mask > 0.5)

        if len(needle_points) == 0:
            return None, None, None, None

        # 各点から中心までの距離を計算
        distances = np.sqrt(
            (needle_points[:, 1] - center_x) ** 2
            + (needle_points[:, 0] - center_y) ** 2
        )

        # 最も遠い点を先端、最も近い点を基部とする
        max_idx = np.argmax(distances)
        min_idx = np.argmin(distances)

        tip_y, tip_x = needle_points[max_idx]
        base_y, base_x = needle_points[min_idx]

        return int(tip_x), int(tip_y), int(base_x), int(base_y)

    def apply_gradient_and_arrow(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        center_x: int,
        center_y: int,
        tip_x: int,
        tip_y: int,
        base_x: int,
        base_y: int,
    ) -> np.ndarray:
        """
        グラデーション + 矢印を適用

        Args:
            image: 元画像
            mask: 針のマスク
            center_x, center_y: ゲージ中心
            tip_x, tip_y: 針の先端座標
            base_x, base_y: 針の基部座標

        Returns:
            処理済み画像
        """
        result = image.copy()

        # 針の領域の座標を取得
        needle_points = np.argwhere(mask > 0.5)

        if len(needle_points) == 0:
            return result

        # 各ピクセルに対してグラデーションを適用
        for point in needle_points:
            y, x = point

            # 基部から先端への距離の割合を計算 (0.0 = 基部, 1.0 = 先端)
            dist_from_base = np.sqrt((x - base_x) ** 2 + (y - base_y) ** 2)
            total_length = np.sqrt((tip_x - base_x) ** 2 + (tip_y - base_y) ** 2)

            if total_length > 0:
                ratio = min(1.0, dist_from_base / total_length)
            else:
                ratio = 0.0

            # グラデーション: 基部=暗い赤 (0, 0, 100), 先端=明るい黄色 (0, 255, 255)
            # BGRフォーマット
            b = int(0)
            g = int(255 * ratio)
            r = int(100 + 155 * ratio)

            result[y, x] = [b, g, r]

        # 先端に矢印マーカーを追加
        result = self._draw_arrow(result, center_x, center_y, tip_x, tip_y)

        return result

    def apply_arrow_only(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        center_x: int,
        center_y: int,
        tip_x: int,
        tip_y: int,
    ) -> np.ndarray:
        """
        矢印のみを適用（針は赤色のまま）

        Args:
            image: 元画像（赤色オーバーレイ済み）
            mask: 針のマスク
            center_x, center_y: ゲージ中心
            tip_x, tip_y: 針の先端座標

        Returns:
            処理済み画像
        """
        result = image.copy()
        result = self._draw_arrow(result, center_x, center_y, tip_x, tip_y)
        return result

    def apply_red_triangle_marker(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        center_x: int,
        center_y: int,
        tip_x: int,
        tip_y: int,
    ) -> np.ndarray:
        """
        針の先端に赤色の小さな三角形マーカーを描画（針は赤色のまま）

        Args:
            image: 元画像（赤色オーバーレイ済み）
            mask: 針のマスク
            center_x, center_y: ゲージ中心
            tip_x, tip_y: 針の先端座標

        Returns:
            処理済み画像
        """
        result = image.copy()

        # 針の方向ベクトルを計算
        dx = tip_x - center_x
        dy = tip_y - center_y
        length = np.sqrt(dx**2 + dy**2)

        if length > 0:
            # 正規化された方向ベクトル
            dx_norm = dx / length
            dy_norm = dy / length

            # 三角形のサイズ（控えめに）
            triangle_size = 12

            # 三角形の先端位置（針の先端のすぐ外側）
            triangle_tip_x = int(tip_x + dx_norm * 8)
            triangle_tip_y = int(tip_y + dy_norm * 8)

            # 三角形の両翼の位置
            perpendicular_x = -dy_norm
            perpendicular_y = dx_norm

            wing1_x = int(
                triangle_tip_x
                - dx_norm * triangle_size
                + perpendicular_x * (triangle_size * 0.6)
            )
            wing1_y = int(
                triangle_tip_y
                - dy_norm * triangle_size
                + perpendicular_y * (triangle_size * 0.6)
            )

            wing2_x = int(
                triangle_tip_x
                - dx_norm * triangle_size
                - perpendicular_x * (triangle_size * 0.6)
            )
            wing2_y = int(
                triangle_tip_y
                - dy_norm * triangle_size
                - perpendicular_y * (triangle_size * 0.6)
            )

            # 小さな三角形を描画（明るい赤色で針と区別）
            triangle_points = np.array(
                [[triangle_tip_x, triangle_tip_y], [wing1_x, wing1_y], [wing2_x, wing2_y]],
                np.int32,
            )
            cv2.fillPoly(result, [triangle_points], (0, 0, 255))  # 明るい赤色

        return result

    def _draw_arrow(
        self,
        image: np.ndarray,
        center_x: int,
        center_y: int,
        tip_x: int,
        tip_y: int,
    ) -> np.ndarray:
        """
        矢印を描画（内部ヘルパー関数）

        Args:
            image: 画像
            center_x, center_y: ゲージ中心
            tip_x, tip_y: 針の先端座標

        Returns:
            矢印描画済み画像
        """
        result = image.copy()

        # 針の方向ベクトルを計算
        dx = tip_x - center_x
        dy = tip_y - center_y
        length = np.sqrt(dx**2 + dy**2)

        if length > 0:
            # 正規化された方向ベクトル
            dx_norm = dx / length
            dy_norm = dy / length

            # 矢印のサイズ
            arrow_length = 30
            arrow_width = 15

            # 矢印の先端位置（針の先端からさらに延長）
            arrow_tip_x = int(tip_x + dx_norm * 20)
            arrow_tip_y = int(tip_y + dy_norm * 20)

            # 矢印の両翼の位置
            perpendicular_x = -dy_norm
            perpendicular_y = dx_norm

            wing1_x = int(
                arrow_tip_x - dx_norm * arrow_length + perpendicular_x * arrow_width
            )
            wing1_y = int(
                arrow_tip_y - dy_norm * arrow_length + perpendicular_y * arrow_width
            )

            wing2_x = int(
                arrow_tip_x - dx_norm * arrow_length - perpendicular_x * arrow_width
            )
            wing2_y = int(
                arrow_tip_y - dy_norm * arrow_length - perpendicular_y * arrow_width
            )

            # 矢印を描画（黄色）
            arrow_points = np.array(
                [[arrow_tip_x, arrow_tip_y], [wing1_x, wing1_y], [wing2_x, wing2_y]],
                np.int32,
            )
            cv2.fillPoly(result, [arrow_points], (0, 255, 255))
            cv2.polylines(result, [arrow_points], True, (0, 200, 200), 2)

        return result

    def process_image(
        self, image: np.ndarray
    ) -> Tuple[np.ndarray, str]:
        """
        画像を処理（triangle固定）

        Args:
            image: 入力画像 (BGR)

        Returns:
            (処理済み画像, メッセージ)
        """
        if self.model is None:
            raise RuntimeError("モデルが読み込まれていません。load_model()を先に実行してください。")

        h, w, _ = image.shape

        # ゲージ中心を画像中心と仮定
        center_x = w // 2
        center_y = h // 2

        # YOLOでセグメンテーション
        results = self.model(
            image, conf=self.conf_threshold, iou=self.iou_threshold
        )
        result = results[0]
        output_image = image.copy()

        if result.masks is None:
            return output_image, "針が検出されませんでした"

        for r in results:
            boxes = r.boxes

        for i, (seg, box) in enumerate(zip(result.masks.data.cpu().numpy(), boxes)):
            seg = cv2.resize(seg, (w, h))

            # 針の先端と基部を検出
            tip_x, tip_y, base_x, base_y = self.detect_needle_tip(
                seg, center_x, center_y
            )

            if tip_x is not None:
                # 通常の赤色オーバーレイ
                output_image = self.overlay(output_image, seg, self.color, 0.5)
                # 赤色の小さな三角形マーカーを適用
                output_image = self.apply_red_triangle_marker(
                    output_image, seg, center_x, center_y, tip_x, tip_y
                )
            else:
                # フォールバック: 通常の赤色オーバーレイ
                output_image = self.overlay(output_image, seg, self.color, 0.5)
                return output_image, f"警告: 針の先端を検出できませんでした（画像{i+1}）"

        return output_image, "処理成功"
