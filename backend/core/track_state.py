import os
import logging

logger = logging.getLogger('video_pipeline')


class TrackStateManager:
    """Track ID kararliligini izler; ani konum sicramalarini tespit eder."""

    def __init__(self):
        self.max_jump_px = float(os.getenv('TRACK_MAX_JUMP_PX', 100))
        self._last_centers: dict[int, tuple[float, float]] = {}
        self._frame_counts: dict[int, int] = {}

    def update(self, track_id: int, bbox: list) -> dict:
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        jumped = False

        if track_id in self._last_centers:
            lx, ly = self._last_centers[track_id]
            dist = ((cx - lx) ** 2 + (cy - ly) ** 2) ** 0.5
            if dist > self.max_jump_px:
                jumped = True
                logger.warning(
                    f"Track ID sicramasi | id={track_id} | mesafe={dist:.0f}px "
                    f"(esik={self.max_jump_px:.0f}) — kinematik sifirlanacak"
                )

        self._last_centers[track_id] = (cx, cy)
        self._frame_counts[track_id] = self._frame_counts.get(track_id, 0) + 1

        return {
            'id_jump': jumped,
            'frame_count': self._frame_counts[track_id],
            'center': (cx, cy),
            'is_stable': self._frame_counts[track_id] >= int(os.getenv('TRACK_STABLE_FRAMES', 5)),
        }

    def clear_stale(self, active_ids: set):
        stale = [tid for tid in self._last_centers if tid not in active_ids]
        for tid in stale:
            self._last_centers.pop(tid, None)
            self._frame_counts.pop(tid, None)
