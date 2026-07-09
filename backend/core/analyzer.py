import os
import json
import logging
import time
import cv2
import numpy as np

logger = logging.getLogger('video_pipeline')


class AnomalyAnalyzer:
    """Esik tabanli anomali siniflandirici: dusme, kosma, alan ihlali."""

    ANOMALY_FALL = 'FALL'
    ANOMALY_RUN = 'RUN'
    ANOMALY_ZONE = 'ZONE_VIOLATION'
    ANOMALY_PRESENCE = 'PERSON_ENTERED'

    def __init__(self):
        self.fall_vy = float(os.getenv('FALL_VERTICAL_VELOCITY', 120))
        self.fall_spine = float(os.getenv('FALL_SPINE_ANGLE', 30))
        self.run_speed = float(os.getenv('RUN_HORIZONTAL_SPEED', 90))
        self.cooldown = float(os.getenv('ANOMALY_COOLDOWN_SEC', 12))
        self.min_samples = int(os.getenv('MIN_KINEMATICS_SAMPLES', 4))
        self.presence_enabled = os.getenv('ENABLE_PRESENCE_ALERT', 'false').lower() == 'true'
        self.presence_cooldown = float(os.getenv('PRESENCE_COOLDOWN_SEC', 30))
        self.zone_bbox_fallback = os.getenv('ZONE_BBOX_FALLBACK', 'false').lower() == 'true'
        self.frame_w = float(os.getenv('FRAME_WIDTH', 640))
        self.frame_h = float(os.getenv('FRAME_HEIGHT', 480))
        self._known_tracks: set[int] = set()

        self._last_alert: dict[str, float] = {}
        self._zones = self._load_zones()

    def _load_zones(self) -> dict:
        path = os.getenv('ZONE_CONFIG_PATH', 'config/zones.json')
        if not os.path.isabs(path):
            root = os.path.join(os.path.dirname(__file__), '..', '..')
            path = os.path.normpath(os.path.join(root, path))

        if not os.path.exists(path):
            logger.warning(f"Zone config bulunamadi: {path}")
            return {}

        with open(path, encoding='utf-8') as f:
            return json.load(f)

    def _cooldown_ok(self, key: str, seconds: float | None = None) -> bool:
        now = time.time()
        wait = seconds if seconds is not None else self.cooldown
        last = self._last_alert.get(key, 0)
        if now - last < wait:
            return False
        self._last_alert[key] = now
        return True

    def analyze(
        self,
        track_id: int,
        metrics: dict,
        hip_center: dict,
        camera_id: str
    ) -> dict | None:
        """Kinematik metriklere gore anomali karari uretir."""
        if metrics.get('sample_count', 0) < self.min_samples:
            return None

        vy = metrics.get('vertical_velocity', 0)
        vx = metrics.get('horizontal_velocity', 0)
        spine = metrics.get('spine_angle', 90)
        h_speed = abs(vx)
        # Piksel/sn -> kare genisligine gore normalize (640px baz)
        norm_h_speed = h_speed * (640.0 / max(self.frame_w, 1))
        norm_vy = vy * (480.0 / max(self.frame_h, 1))

        anomaly_type = None
        confidence = 0.0

        if norm_h_speed >= self.run_speed:
            anomaly_type = self.ANOMALY_RUN
            confidence = min(1.0, norm_h_speed / self.run_speed * 0.85)

        elif norm_vy >= self.fall_vy and spine <= self.fall_spine:
            anomaly_type = self.ANOMALY_FALL
            confidence = min(1.0, norm_vy / self.fall_vy * 0.5 + (90 - spine) / 90 * 0.5)

        elif self._check_zone_violation(hip_center, camera_id):
            anomaly_type = self.ANOMALY_ZONE
            confidence = 0.85

        if not anomaly_type:
            return None

        key = f"{camera_id}_{track_id}_{anomaly_type}"
        if not self._cooldown_ok(key):
            return None

        event = {
            'camera_id': camera_id,
            'track_id': track_id,
            'anomaly_type': anomaly_type,
            'confidence_score': round(confidence, 3),
            'metrics': metrics,
            'hip_center': hip_center,
            'timestamp': time.time()
        }
        logger.info(
            f"ANOMALI | {anomaly_type} | cam={camera_id} | track={track_id} | conf={confidence:.2f}"
        )
        return event

    def analyze_presence(self, track_id: int, camera_id: str, bbox: list) -> dict | None:
        """Yeni kisi kareye girdiginde tetiklenir (opsiyonel)."""
        if not self.presence_enabled:
            return None
        if track_id in self._known_tracks:
            return None
        self._known_tracks.add(track_id)

        key = f"{camera_id}_{track_id}_presence"
        if not self._cooldown_ok(key, self.presence_cooldown):
            return None

        x1, y1, x2, y2 = bbox
        event = {
            'camera_id': camera_id,
            'track_id': track_id,
            'anomaly_type': self.ANOMALY_PRESENCE,
            'confidence_score': 0.9,
            'metrics': {},
            'hip_center': {'x': (x1 + x2) / 2, 'y': (y1 + y2) / 2, 'z': 0},
            'timestamp': time.time()
        }
        logger.info(f"ANOMALI | PERSON_ENTERED | cam={camera_id} | track={track_id}")
        return event

    def analyze_zone_bbox(self, track_id: int, bbox: list, camera_id: str) -> dict | None:
        """Pose olmadan bbox merkezi ile alan ihlali (varsayilan kapali)."""
        if not self.zone_bbox_fallback:
            return None
        x1, y1, x2, y2 = bbox
        center = {'x': (x1 + x2) / 2, 'y': (y1 + y2) / 2, 'z': 0}
        if not self._check_zone_violation(center, camera_id):
            return None
        key = f"{camera_id}_{track_id}_{self.ANOMALY_ZONE}"
        if not self._cooldown_ok(key):
            return None
        return {
            'camera_id': camera_id,
            'track_id': track_id,
            'anomaly_type': self.ANOMALY_ZONE,
            'confidence_score': 0.85,
            'metrics': {},
            'hip_center': center,
            'timestamp': time.time()
        }

    def clear_tracks(self, active_ids: set):
        """Ekrandan cikan track ID'lerini temizler — tekrar girince bildirim gelir."""
        self._known_tracks &= active_ids

    def _check_zone_violation(self, hip_center: dict, camera_id: str) -> bool:
        forbidden = self._zones.get(camera_id, [])
        if not forbidden:
            return False

        point = (float(hip_center['x']), float(hip_center['y']))

        for polygon in forbidden:
            pts = np.array(polygon, dtype=np.int32)
            result = cv2.pointPolygonTest(pts, point, False)
            if result >= 0:
                return True

        return False

    def get_zones_for_camera(self, camera_id: str) -> list:
        return self._zones.get(camera_id, [])
