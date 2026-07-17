import os
import logging
from deep_sort_realtime.deepsort_tracker import DeepSort

logger = logging.getLogger('video_pipeline')


class PersonTracker:
    """DeepSORT tabanli coklu nesne takip katmani."""

    def __init__(self):
        max_age = int(os.getenv('DEEPSORT_MAX_AGE', 45))
        n_init = int(os.getenv('DEEPSORT_N_INIT', 5))
        max_cosine = float(os.getenv('DEEPSORT_MAX_COSINE_DIST', 0.15))
        max_iou = float(os.getenv('DEEPSORT_MAX_IOU_DIST', 0.55))
        nms_overlap = float(os.getenv('DEEPSORT_NMS_OVERLAP', 0.7))

        self.tracker = DeepSort(
            max_age=max_age,
            n_init=n_init,
            max_cosine_distance=max_cosine,
            max_iou_distance=max_iou,
            nms_max_overlap=nms_overlap,
            embedder='mobilenet',
            half=True,
            embedder_gpu=os.getenv('USE_GPU', 'true').lower() == 'true',
        )
        logger.info(
            f"DeepSORT baslatildi | max_age={max_age} | n_init={n_init} | "
            f"cosine={max_cosine} | iou={max_iou}"
        )

    def update(self, detections: list, frame) -> list:
        """
        YOLO tespitlerini takip ID'leri ile eslestirir.

        Returns:
            list: track_id, bbox, confidence, is_confirmed
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
                'class': 'person',
                'is_confirmed': True,
            })

        if tracked:
            logger.debug(f"{len(tracked)} takip | ID'ler: {[t['track_id'] for t in tracked]}")

        return tracked
