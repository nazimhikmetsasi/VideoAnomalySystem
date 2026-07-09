import os
import logging
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger('video_pipeline')

# COCO pose indeksleri (YOLOv8-pose, 17 nokta)
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_HIP = 11
RIGHT_HIP = 12


class PoseEstimator:
    """YOLOv8-pose ile iskelet noktasi cikarimi."""

    def __init__(self):
        model_path = os.getenv('POSE_MODEL_PATH', 'yolov8n-pose.pt')
        device = 'cuda' if os.getenv('USE_GPU', 'true').lower() == 'true' else 'cpu'
        logger.info(f"YOLOv8-pose yukleniyor: {model_path} | device={device}")
        self.model = YOLO(model_path)
        self.model.to(device)
        self.conf = float(os.getenv('POSE_MIN_DETECTION_CONF', 0.25))
        logger.info("Pose estimator baslatildi.")

    def extract(self, frame: np.ndarray, bbox: list) -> dict | None:
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        results = self.model(crop, conf=self.conf, verbose=False)
        if not results or results[0].keypoints is None:
            return None

        kpts_xy = results[0].keypoints.xy
        if kpts_xy is None or len(kpts_xy) == 0:
            return None

        points = kpts_xy[0].cpu().numpy()
        confs = None
        if results[0].keypoints.conf is not None:
            confs = results[0].keypoints.conf[0].cpu().numpy()

        crop_w, crop_h = x2 - x1, y2 - y1
        raw = []
        for i, (px, py) in enumerate(points):
            if px == 0 and py == 0:
                vis = 0.0
            else:
                vis = float(confs[i]) if confs is not None else 1.0
            raw.append({
                'x': float(px + x1),
                'y': float(py + y1),
                'z': 0.0,
                'visibility': vis
            })

        if raw[LEFT_HIP]['visibility'] < 0.2 or raw[RIGHT_HIP]['visibility'] < 0.2:
            return None

        lh = raw[LEFT_HIP]
        rh = raw[RIGHT_HIP]
        origin_x = (lh['x'] + rh['x']) / 2
        origin_y = (lh['y'] + rh['y']) / 2

        normalized = [{
            'x': round(pt['x'] - origin_x, 2),
            'y': round(pt['y'] - origin_y, 2),
            'z': 0.0,
            'visibility': round(pt['visibility'], 3)
        } for pt in raw]

        return {
            'landmarks': normalized,
            'raw_landmarks': raw,
            'hip_center': {'x': origin_x, 'y': origin_y, 'z': 0.0}
        }

    def spine_angle(self, landmarks: list) -> float:
        ls = landmarks[LEFT_SHOULDER]
        rs = landmarks[RIGHT_SHOULDER]
        lh = landmarks[LEFT_HIP]
        rh = landmarks[RIGHT_HIP]

        if min(ls['visibility'], rs['visibility'], lh['visibility'], rh['visibility']) < 0.3:
            return 90.0

        shoulder_x = (ls['x'] + rs['x']) / 2
        shoulder_y = (ls['y'] + rs['y']) / 2
        hip_x = (lh['x'] + rh['x']) / 2
        hip_y = (lh['y'] + rh['y']) / 2

        dx = shoulder_x - hip_x
        dy = shoulder_y - hip_y

        if dx == 0 and dy == 0:
            return 90.0

        return round(abs(np.degrees(np.arctan2(abs(dx), abs(dy) + 1e-6))), 2)

    def close(self):
        pass
