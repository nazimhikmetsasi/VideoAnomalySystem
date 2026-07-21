import os
import json
import logging
import time
import cv2
import numpy as np

from core.motion_classifier import (
    MotionClassifier,
    MOTION_RUNNING,
    MOTION_FALLING,
)

logger = logging.getLogger('video_pipeline')


class AnomalyAnalyzer:
    """Esik tabanli anomali siniflandirici: dusme, kosma, alan ihlali."""

    ANOMALY_FALL = 'FALL'
    ANOMALY_RUN = 'RUN'
    ANOMALY_ZONE = 'ZONE_VIOLATION'
    ANOMALY_PRESENCE = 'PERSON_ENTERED'

    def __init__(self):
        self.fall_vy = float(os.getenv('FALL_VERTICAL_VELOCITY', 70))
        self.fall_spine = float(os.getenv('FALL_SPINE_ANGLE', 40))
        self.run_speed = float(os.getenv('RUN_HORIZONTAL_SPEED', 65))
        self.cooldown = float(os.getenv('ANOMALY_COOLDOWN_SEC', 18))
        self.min_samples = int(os.getenv('MIN_KINEMATICS_SAMPLES', 8))
        self.presence_enabled = os.getenv('ENABLE_PRESENCE_ALERT', 'false').lower() == 'true'
        self.presence_cooldown = float(os.getenv('PRESENCE_COOLDOWN_SEC', 30))
        self.zone_bbox_fallback = os.getenv('ZONE_BBOX_FALLBACK', 'false').lower() == 'true'
        # Tek kare hiz sicramasini engelle: RUN/FALL icin onayli hareket iste
        self.require_motion_confirm = os.getenv('REQUIRE_MOTION_CONFIRM', 'true').lower() == 'true'
        self.zone_dwell_frames = int(os.getenv('ZONE_DWELL_FRAMES', 10))
        self.min_run_conf = float(os.getenv('MIN_RUN_CONFIDENCE', 0.55))
        self.frame_w = float(os.getenv('FRAME_WIDTH', 640))
        self.frame_h = float(os.getenv('FRAME_HEIGHT', 480))
        self._known_tracks: set[int] = set()
        self._zone_dwell: dict[str, int] = {}
        self.motion_classifier = MotionClassifier()

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

    def _zone_dwell_ok(self, camera_id: str, track_id: int, inside: bool) -> bool:
        """Bolgede art arda N kare kalinca ihlal say."""
        key = f'{camera_id}_{track_id}'
        if not inside:
            self._zone_dwell[key] = 0
            return False
        self._zone_dwell[key] = self._zone_dwell.get(key, 0) + 1
        return self._zone_dwell[key] >= self.zone_dwell_frames

    def analyze(
        self,
        track_id: int,
        metrics: dict,
        hip_center: dict,
        camera_id: str,
        pose_features: dict | None = None,
        motion_info: dict | None = None,
    ) -> dict | None:
        """Kinematik metriklere gore anomali karari uretir."""
        if metrics.get('sample_count', 0) < self.min_samples:
            return None

        if motion_info is None:
            motion_info = self.motion_classifier.classify(track_id, metrics, pose_features)
        metrics = {**metrics, **motion_info}

        vy = metrics.get('vertical_velocity', 0)
        vx = metrics.get('horizontal_velocity', 0)
        spine = metrics.get('spine_angle', 90)
        h_speed = abs(vx)
        norm_h_speed = h_speed * (640.0 / max(self.frame_w, 1))
        norm_vy = vy * (480.0 / max(self.frame_h, 1))

        confirmed = motion_info.get('motion_confirmed')
        motion_conf = float(motion_info.get('motion_confidence') or 0)
        anomaly_type = None
        confidence = 0.0

        run_hit = False
        if self.require_motion_confirm:
            run_hit = (
                confirmed == MOTION_RUNNING
                and norm_h_speed >= self.run_speed * 0.75
                and motion_conf >= self.min_run_conf
            )
        else:
            run_hit = confirmed == MOTION_RUNNING or norm_h_speed >= self.run_speed

        # Dusme: dikey baskin + omurga egik + yatay kosu YOK
        fall_like = (
            norm_vy >= self.fall_vy
            and spine <= self.fall_spine
            and norm_h_speed < self.run_speed * 0.6
        )
        if self.require_motion_confirm:
            fall_hit = confirmed == MOTION_FALLING and fall_like
        else:
            fall_hit = confirmed == MOTION_FALLING or fall_like

        # Yuksek yatay hiz varken dusmeyi ezer (kosu salinimi / kamera sarsintisi)
        if norm_h_speed >= self.run_speed * 0.75:
            fall_hit = False

        inside_zone = self._check_zone_violation(hip_center, camera_id)
        zone_hit = self._zone_dwell_ok(camera_id, track_id, inside_zone)

        # Oncelik: RUN > FALL > ZONE
        if run_hit:
            anomaly_type = self.ANOMALY_RUN
            confidence = min(1.0, max(motion_conf, norm_h_speed / self.run_speed * 0.85))
        elif fall_hit:
            anomaly_type = self.ANOMALY_FALL
            confidence = min(
                1.0,
                max(
                    motion_conf,
                    norm_vy / max(self.fall_vy, 1) * 0.5 + (90 - spine) / 90 * 0.5,
                ),
            )
        elif zone_hit:
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
            'motion': motion_info.get('motion'),
            'motion_confirmed': confirmed,
            'metrics': metrics,
            'hip_center': hip_center,
            'timestamp': time.time()
        }
        logger.info(
            f"ANOMALI | {anomaly_type} | cam={camera_id} | track={track_id} | "
            f"motion={motion_info.get('motion')} | conf={confidence:.2f}"
        )
        return event

    def reset_track(self, track_id: int):
        self.motion_classifier.reset_track(track_id)
        stale = [k for k in self._zone_dwell if k.endswith(f'_{track_id}')]
        for k in stale:
            del self._zone_dwell[k]

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
        inside = self._check_zone_violation(center, camera_id)
        if not self._zone_dwell_ok(camera_id, track_id, inside):
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
        self.motion_classifier.clear_stale(active_ids)
        self._zone_dwell = {
            k: v for k, v in self._zone_dwell.items()
            if any(k.endswith(f'_{tid}') for tid in active_ids)
        }

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
