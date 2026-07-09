import os
import logging
from deep_sort_realtime.deepsort_tracker import DeepSort

logger = logging.getLogger('video_pipeline')


class PersonTracker:
    """DeepSORT tabanli coklu nesne takip katmani."""

    def __init__(self):
        max_age = int(os.getenv('DEEPSORT_MAX_AGE', 30))
        n_init = int(os.getenv('DEEPSORT_N_INIT', 3))

        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            embedder='mobilenet',
            half=True,
            embedder_gpu=os.getenv('USE_GPU', 'true').lower() == 'true'
        )
        logger.info(f"DeepSORT baslatildi | max_age={max_age} | n_init={n_init}")

    def update(self, detections: list, frame) -> list:
        """
        YOLO tespitlerini takip ID'leri ile eslestirir.

        Args:
            detections: [{"bbox": [x1,y1,x2,y2], "confidence": float, "class": "person"}, ...]
            frame: BGR numpy array

        Returns:
            list: track_id eklenmis tespit listesi
        """
        raw = [
            (det['bbox'], det['confidence'], det['class'])
            for det in detections
        ]

        tracks = self.tracker.update_tracks(raw, frame=frame)
        tracked = []

        for track in tracks:
            if not track.is_confirmed():
                continue

            ltrb = track.to_ltrb()
            track_id = track.track_id
            x1, y1, x2, y2 = map(int, ltrb)

            tracked.append({
                'track_id': track_id,
                'bbox': [x1, y1, x2, y2],
                'confidence': round(float(track.det_conf or 0.0), 3),
                'class': 'person'
            })

        if tracked:
            logger.debug(f"{len(tracked)} takip edilen kisi | ID'ler: {[t['track_id'] for t in tracked]}")

        return tracked
