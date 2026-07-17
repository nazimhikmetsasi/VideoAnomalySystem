import os
import logging
from collections import deque
import numpy as np

logger = logging.getLogger('video_pipeline')


class KinematicsEngine:
    """Track ID bazli kayan pencere kinematik metrik hesaplayici."""

    def __init__(self):
        self.window_size = int(os.getenv('KINEMATICS_WINDOW_SIZE', 30))
        self._buffers: dict[int, deque] = {}

    def _get_buffer(self, track_id: int) -> deque:
        if track_id not in self._buffers:
            self._buffers[track_id] = deque(maxlen=self.window_size)
        return self._buffers[track_id]

    def update(self, track_id: int, hip_center: dict, spine_angle: float, timestamp: float) -> dict:
        """
        Yeni kare verisini tampona ekler ve kinematik metrikleri hesaplar.
        """
        buf = self._get_buffer(track_id)
        buf.append({
            'hip_x': hip_center['x'],
            'hip_y': hip_center['y'],
            'spine_angle': spine_angle,
            'timestamp': timestamp
        })

        metrics = {
            'track_id': track_id,
            'vertical_velocity': 0.0,
            'horizontal_velocity': 0.0,
            'vertical_acceleration': 0.0,
            'spine_angle': spine_angle,
            'sample_count': len(buf)
        }

        if len(buf) < 2:
            return metrics

        prev = buf[-2]
        curr = buf[-1]
        dt = curr['timestamp'] - prev['timestamp']
        if dt <= 0:
            dt = 0.033

        vy = (curr['hip_y'] - prev['hip_y']) / dt
        vx = (curr['hip_x'] - prev['hip_x']) / dt

        # Son birkaç kare ortalamasi — tek kare gürültüsünü azaltir
        n = min(len(buf) - 1, 5)
        vxs, vys = [], []
        for i in range(1, n + 1):
            c = buf[-i]
            p = buf[-i - 1]
            dt_i = c['timestamp'] - p['timestamp']
            if dt_i <= 0:
                continue
            vxs.append((c['hip_x'] - p['hip_x']) / dt_i)
            vys.append((c['hip_y'] - p['hip_y']) / dt_i)
        if vxs:
            vx = float(np.mean(vxs))
            vy = float(np.mean(vys))

        metrics['vertical_velocity'] = round(vy, 2)
        metrics['horizontal_velocity'] = round(vx, 2)

        if len(buf) >= 3:
            prev2 = buf[-3]
            dt2 = prev['timestamp'] - prev2['timestamp']
            if dt2 > 0:
                prev_vy = (prev['hip_y'] - prev2['hip_y']) / dt2
                metrics['vertical_acceleration'] = round((vy - prev_vy) / dt, 2)

        return metrics

    def reset_track(self, track_id: int):
        """ID sicramasi veya karisiklik sonrasi tamponu sifirlar."""
        self._buffers.pop(track_id, None)

    def clear_stale(self, active_ids: set):
        """Aktif olmayan track tamponlarini temizler."""
        stale = [tid for tid in self._buffers if tid not in active_ids]
        for tid in stale:
            del self._buffers[tid]
