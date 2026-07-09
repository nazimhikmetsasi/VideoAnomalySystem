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

    def __init__(self):
        # Görüntüde y aşağı doğru arttığı için düşme = pozitif dikey hız
        self.fall_vy = float(os.getenv('FALL_VERTICAL_VELOCITY', 60))
        self.fall_spine = float(os.getenv('FALL_SPINE_ANGLE', 45))
        self.run_speed = float(os.getenv('RUN_HORIZONTAL_SPEED', 40))
        self.cooldown = float(os.getenv('ANOMALY_COOLDOWN_SEC', 3))

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

    def _cooldown_ok(self, key: str) -> bool:
        now = time.time()
        last = self._last_alert.get(key, 0)
        if now - last < self.cooldown:
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
        vy = metrics.get('vertical_velocity', 0)
        vx = metrics.get('horizontal_velocity', 0)
        spine = metrics.get('spine_angle', 90)
        h_speed = abs(vx)

        anomaly_type = None
        confidence = 0.0

        # Kosma: yuksek yatay hiz (once kontrol — daha kolay tetiklenir)
        if h_speed >= self.run_speed:
            anomaly_type = self.ANOMALY_RUN
            confidence = min(1.0, h_speed / self.run_speed * 0.8)

        # Alan ihlali
        elif self._check_zone_violation(hip_center, camera_id):
            anomaly_type = self.ANOMALY_ZONE
            confidence = 0.85

        # Dusme: ani asagi hiz + omurga yataylasmasi
        elif vy >= self.fall_vy and spine <= self.fall_spine:
            anomaly_type = self.ANOMALY_FALL
            confidence = min(1.0, vy / self.fall_vy * 0.5 + (90 - spine) / 90 * 0.5)

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
