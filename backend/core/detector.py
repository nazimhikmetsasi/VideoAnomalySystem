import os
import logging
from pathlib import Path
from ultralytics import YOLO
import cv2
import numpy as np

logger = logging.getLogger('video_pipeline')

ROOT = Path(__file__).resolve().parents[2]


def _bbox_iou(a: list, b: list) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)


def _bbox_containment(a: list, b: list) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    small = min(area_a, area_b)
    if small <= 1:
        return 0.0
    return inter / small


def _centers_close(a: list, b: list, factor: float = 0.5) -> bool:
    cax = (a[0] + a[2]) / 2.0
    cay = (a[1] + a[3]) / 2.0
    cbx = (b[0] + b[2]) / 2.0
    cby = (b[1] + b[3]) / 2.0
    dist = ((cax - cbx) ** 2 + (cay - cby) ** 2) ** 0.5
    ref = max(a[3] - a[1], b[3] - b[1], 1.0)
    return dist <= ref * factor


def _bbox_area(b: list) -> float:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def merge_overlapping_detections(
    detections: list,
    iou_thr: float = 0.5,
    contain_thr: float = 0.7,
    near_factor: float = 0.0,
) -> list:
    """Ust uste kutularda yuksek guveni tut; union ile buyutme."""
    if len(detections) <= 1:
        return detections
    ordered = sorted(detections, key=lambda d: d['confidence'], reverse=True)
    kept: list = []
    for det in ordered:
        dup = False
        for i, k in enumerate(kept):
            iou = _bbox_iou(det['bbox'], k['bbox'])
            cont = _bbox_containment(det['bbox'], k['bbox'])
            if iou >= iou_thr or cont >= contain_thr:
                # Union yok — kutuyu sisirme; daha guvenli / kucuk makul kutuyu tut
                if det['confidence'] > k['confidence'] or (
                    abs(det['confidence'] - k['confidence']) < 0.05
                    and _bbox_area(det['bbox']) < _bbox_area(k['bbox'])
                ):
                    kept[i] = {**det}
                dup = True
                break
        if not dup:
            kept.append(det)
    return kept


def _resolve_model_path(raw: str) -> str:
    p = Path(raw)
    if p.is_file():
        return str(p)
    cand = ROOT / raw
    if cand.is_file():
        return str(cand)
    return raw


class HumanDetector:
    def __init__(self):
        model_path = _resolve_model_path(os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt'))
        self.conf_threshold = float(os.getenv('YOLO_CONF_THRESHOLD', 0.25))
        self.iou_threshold = float(os.getenv('YOLO_IOU_THRESHOLD', 0.35))
        self.merge_iou = float(os.getenv('DET_MERGE_IOU', 0.5))
        self.merge_contain = float(os.getenv('DET_MERGE_CONTAIN', 0.7))
        self.merge_near = 0.0
        self.device = 'cuda' if os.getenv('USE_GPU', 'true').lower() == 'true' else 'cpu'

        logger.info(f"YOLOv8 modeli yükleniyor: {model_path} | Device: {self.device}")
        self.model = YOLO(model_path)
        self.model.to(self.device)
        logger.info(f"YOLOv8 modeli yüklendi. conf={self.conf_threshold} | iou={self.iou_threshold}")

    def detect(self, frame: np.ndarray) -> list:
        results = self.model(
            frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            classes=[0],
            verbose=False,
        )

        fh, fw = frame.shape[:2]
        frame_area = float(max(fh * fw, 1))
        max_area_ratio = float(os.getenv('DET_MAX_AREA_RATIO', 0.55))
        max_aspect = float(os.getenv('DET_MAX_ASPECT', 4.0))

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                bw, bh = max(0, x2 - x1), max(0, y2 - y1)
                area = bw * bh
                aspect = bw / max(bh, 1)
                # Sadece asiri buyuk FP (kulube/araba); normal kisi elenmesin
                if area > frame_area * max_area_ratio or aspect > max_aspect or aspect < 0.12:
                    continue
                confidence = float(box.conf[0])
                detections.append({
                    'bbox': [x1, y1, x2, y2],
                    'confidence': round(confidence, 3),
                    'class': 'person',
                })

        before = len(detections)
        detections = merge_overlapping_detections(
            detections,
            iou_thr=self.merge_iou,
            contain_thr=self.merge_contain,
            near_factor=self.merge_near,
        )
        if before != len(detections):
            logger.debug(f"Cift kutu birlesti: {before} -> {len(detections)}")

        return detections

    def draw_detections(self, frame: np.ndarray, detections: list) -> np.ndarray:
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame, f'person {conf:.2f}', (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
            )
        cv2.putText(
            frame, f'Kisi Sayisi: {len(detections)}', (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2,
        )
        return frame
