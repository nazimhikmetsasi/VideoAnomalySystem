import os
import logging
from collections import deque

logger = logging.getLogger('video_pipeline')

MOTION_STANDING = 'STANDING'
MOTION_WALKING = 'WALKING'
MOTION_RUNNING = 'RUNNING'
MOTION_FALLING = 'FALLING'
MOTION_SITTING = 'SITTING'
MOTION_CROUCHING = 'CROUCHING'
MOTION_UNKNOWN = 'UNKNOWN'


class MotionClassifier:
    """Pose + kinematik veriden anlik hareket durumu cikarir."""

    def __init__(self):
        self.walk_speed = float(os.getenv('WALK_SPEED_MIN', 15))
        self.run_speed = float(os.getenv('RUN_HORIZONTAL_SPEED', 65))
        self.fall_vy = float(os.getenv('FALL_VERTICAL_VELOCITY', 70))
        self.fall_spine = float(os.getenv('FALL_SPINE_ANGLE', 40))
        self.sit_knee_angle = float(os.getenv('SIT_KNEE_ANGLE_MAX', 95))
        self.crouch_spine = float(os.getenv('CROUCH_SPINE_ANGLE_MAX', 55))
        self.confirm_frames = int(os.getenv('MOTION_CONFIRM_FRAMES', 5))
        self.frame_w = float(os.getenv('FRAME_WIDTH', 640))
        self.frame_h = float(os.getenv('FRAME_HEIGHT', 480))
        self._history: dict[int, deque] = {}

    def _norm_speed(self, vx: float) -> float:
        return abs(vx) * (640.0 / max(self.frame_w, 1))

    def _norm_vy(self, vy: float) -> float:
        return vy * (480.0 / max(self.frame_h, 1))

    def classify(self, track_id: int, metrics: dict, pose_features: dict | None) -> dict:
        """Anlik + onaylanmis hareket durumu dondurur."""
        vx = metrics.get('horizontal_velocity', 0)
        vy = metrics.get('vertical_velocity', 0)
        spine = metrics.get('spine_angle', 90)
        samples = metrics.get('sample_count', 0)

        pf = pose_features or {}
        knee = pf.get('knee_angle_avg', 160)
        hip_knee_ratio = pf.get('hip_knee_ratio', 1.0)

        norm_h = self._norm_speed(vx)
        norm_vy = self._norm_vy(vy)

        instant = MOTION_UNKNOWN
        confidence = 0.3

        if samples < 2:
            instant = MOTION_STANDING
            confidence = 0.4
        elif norm_vy >= self.fall_vy and spine <= self.fall_spine and norm_h < self.run_speed * 0.6:
            # Yatay kosu varken dusme deme (kosu salinimini dusme sanmasin)
            instant = MOTION_FALLING
            confidence = min(1.0, norm_vy / self.fall_vy)
        elif knee <= self.sit_knee_angle and hip_knee_ratio < 0.35:
            instant = MOTION_SITTING
            confidence = 0.75
        elif spine <= self.crouch_spine and norm_h < self.walk_speed:
            instant = MOTION_CROUCHING
            confidence = 0.65
        elif norm_h >= self.run_speed:
            instant = MOTION_RUNNING
            confidence = min(1.0, norm_h / self.run_speed)
        elif norm_h >= self.walk_speed:
            instant = MOTION_WALKING
            confidence = min(0.9, norm_h / self.run_speed)
        else:
            instant = MOTION_STANDING
            confidence = 0.7

        confirmed = self._confirm(track_id, instant)

        return {
            'motion': instant,
            'motion_confirmed': confirmed,
            'motion_confidence': round(confidence, 3),
        }

    def _confirm(self, track_id: int, motion: str) -> str:
        if track_id not in self._history:
            self._history[track_id] = deque(maxlen=self.confirm_frames)
        buf = self._history[track_id]
        buf.append(motion)
        if len(buf) < self.confirm_frames:
            return MOTION_UNKNOWN
        if all(m == motion for m in buf):
            return motion
        return MOTION_UNKNOWN

    def reset_track(self, track_id: int):
        self._history.pop(track_id, None)

    def clear_stale(self, active_ids: set):
        stale = [tid for tid in self._history if tid not in active_ids]
        for tid in stale:
            del self._history[tid]
