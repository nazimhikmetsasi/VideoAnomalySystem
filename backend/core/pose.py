import os
import logging
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger('video_pipeline')

# COCO pose indeksleri (YOLOv8-pose, 17 nokta)
NOSE = 0
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16


def _bbox_iou(a: list, b: list) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)


def _angle_at_joint(a: dict, b: dict, c: dict) -> float:
    """b noktasindaki aci (a-b-c)."""
    ba = np.array([a['x'] - b['x'], a['y'] - b['y']])
    bc = np.array([c['x'] - b['x'], c['y'] - b['y']])
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return 180.0
    cos_angle = np.clip(np.dot(ba, bc) / (norm_ba * norm_bc), -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


class PoseEstimator:
    """YOLOv8-pose ile iskelet noktasi cikarimi — tam kare + track eslestirme."""

    def __init__(self):
        model_path = os.getenv('POSE_MODEL_PATH', 'yolov8n-pose.pt')
        device = 'cuda' if os.getenv('USE_GPU', 'true').lower() == 'true' else 'cpu'
        logger.info(f"YOLOv8-pose yukleniyor: {model_path} | device={device}")
        self.model = YOLO(model_path)
        self.model.to(device)
        self.conf = float(os.getenv('POSE_MIN_DETECTION_CONF', 0.25))
        self._frame_poses: list[dict] = []
        logger.info("Pose estimator baslatildi (tam kare modu).")

    def extract_all(self, frame: np.ndarray) -> list[dict]:
        """Tam karede tum kisilerin pose verisini cikarir."""
        results = self.model(frame, conf=self.conf, verbose=False)
        poses = []

        if not results or results[0].keypoints is None:
            self._frame_poses = []
            return poses

        result = results[0]
        kpts_xy = result.keypoints.xy
        kpts_conf = result.keypoints.conf
        boxes = result.boxes

        if kpts_xy is None or len(kpts_xy) == 0:
            self._frame_poses = []
            return poses

        for i in range(len(kpts_xy)):
            points = kpts_xy[i].cpu().numpy()
            confs = kpts_conf[i].cpu().numpy() if kpts_conf is not None else None

            if boxes is not None and i < len(boxes):
                x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())
            else:
                xs, ys = points[:, 0], points[:, 1]
                valid = (xs > 0) & (ys > 0)
                if not valid.any():
                    continue
                x1, y1 = int(xs[valid].min()), int(ys[valid].min())
                x2, y2 = int(xs[valid].max()), int(ys[valid].max())

            raw = []
            for j, (px, py) in enumerate(points):
                vis = 0.0 if (px == 0 and py == 0) else float(confs[j] if confs is not None else 1.0)
                raw.append({'x': float(px), 'y': float(py), 'z': 0.0, 'visibility': vis})

            if raw[LEFT_HIP]['visibility'] < 0.2 or raw[RIGHT_HIP]['visibility'] < 0.2:
                continue

            lh, rh = raw[LEFT_HIP], raw[RIGHT_HIP]
            origin_x = (lh['x'] + rh['x']) / 2
            origin_y = (lh['y'] + rh['y']) / 2

            normalized = [{
                'x': round(pt['x'] - origin_x, 2),
                'y': round(pt['y'] - origin_y, 2),
                'z': 0.0,
                'visibility': round(pt['visibility'], 3),
            } for pt in raw]

            pose_entry = {
                'bbox': [x1, y1, x2, y2],
                'landmarks': normalized,
                'raw_landmarks': raw,
                'hip_center': {'x': origin_x, 'y': origin_y, 'z': 0.0},
                'features': self._extract_features(raw, [x1, y1, x2, y2]),
            }
            poses.append(pose_entry)

        self._frame_poses = poses
        return poses

    def match_track(self, track_bbox: list, poses: list | None = None) -> dict | None:
        """DeepSORT bbox'ini en iyi pose tespiti ile eslestirir."""
        candidates = poses if poses is not None else self._frame_poses
        if not candidates:
            return None

        best, best_iou = None, 0.0
        for pose in candidates:
            iou = _bbox_iou(track_bbox, pose['bbox'])
            if iou > best_iou:
                best_iou = iou
                best = pose

        min_iou = float(os.getenv('POSE_MATCH_IOU_MIN', 0.15))
        return best if best_iou >= min_iou else None

    def extract(self, frame: np.ndarray, bbox: list) -> dict | None:
        """Geriye uyumluluk: tek bbox icin once tam kare sonra eslestir."""
        if not self._frame_poses:
            self.extract_all(frame)
        return self.match_track(bbox)

    def _extract_features(self, landmarks: list, bbox: list) -> dict:
        ls, rs = landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER]
        lh, rh = landmarks[LEFT_HIP], landmarks[RIGHT_HIP]
        lk, rk = landmarks[LEFT_KNEE], landmarks[RIGHT_KNEE]

        knee_angles = []
        if min(lh['visibility'], lk['visibility']) >= 0.25:
            knee_angles.append(_angle_at_joint(lh, lk, landmarks[LEFT_ANKLE]))
        if min(rh['visibility'], rk['visibility']) >= 0.25:
            knee_angles.append(_angle_at_joint(rh, rk, landmarks[RIGHT_ANKLE]))

        bbox_h = max(bbox[3] - bbox[1], 1)
        hip_y = (lh['y'] + rh['y']) / 2
        knee_y = (lk['y'] + rk['y']) / 2 if knee_angles else hip_y

        return {
            'knee_angle_avg': round(float(np.mean(knee_angles)), 1) if knee_angles else 160.0,
            'hip_knee_ratio': round(abs(hip_y - knee_y) / bbox_h, 3),
            'shoulder_width': round(abs(ls['x'] - rs['x']), 1),
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
