import os
import logging

from deep_sort_realtime.deepsort_tracker import DeepSort

logger = logging.getLogger('video_pipeline')


def _bbox_iou(a: list, b: list) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)


def _bbox_containment(a: list, b: list) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    small = min(area_a, area_b)
    if small <= 1:
        return 0.0
    return inter / small


class PersonTracker:
    """
    Standart DeepSORT takip.

    - Ayni karede gercekten ust uste binen cift kutular birlestirilir (IoU/containment).
    - Konum/yakinlik ile ID birlestirme YOK (ardisik giren farkli kisileri bozuyordu).
    - Video ezber haritasi YOK (tekrar oynatimda yanlis ID veriyordu).
    - Her yeni DeepSORT track = yeni artan display ID (1,2,3...).
    """

    def __init__(self, video_source=None):
        # video_source geriye uyumluluk icin kabul edilir, kullanilmaz
        max_age = int(os.getenv('DEEPSORT_MAX_AGE', 50))
        n_init = int(os.getenv('DEEPSORT_N_INIT', 3))
        max_cosine = float(os.getenv('DEEPSORT_MAX_COSINE_DIST', 0.25))
        max_iou = float(os.getenv('DEEPSORT_MAX_IOU_DIST', 0.7))
        nms_overlap = float(os.getenv('DEEPSORT_NMS_OVERLAP', 0.5))

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
        self._id_map: dict[int, int] = {}  # deepsort_id -> display_id
        self._next_id = 1
        self.merge_iou = float(os.getenv('TRACK_MERGE_IOU', 0.5))
        self.merge_contain = float(os.getenv('TRACK_MERGE_CONTAIN', 0.7))

        logger.info(
            f"DeepSORT baslatildi | max_age={max_age} | n_init={n_init} | "
            f"cosine={max_cosine} | merge_iou={self.merge_iou}"
        )

    def _display_id(self, raw_id: int) -> int:
        if raw_id not in self._id_map:
            self._id_map[raw_id] = self._next_id
            self._next_id += 1
            logger.info(f"Yeni kisi | DeepSORT={raw_id} -> ID={self._id_map[raw_id]}")
        return self._id_map[raw_id]

    def _merge_overlaps(self, items: list) -> list:
        """Sadece ayni karede ust uste binen kutulari birlestir."""
        if len(items) <= 1:
            return items
        items = sorted(items, key=lambda x: x['confidence'], reverse=True)
        kept = []
        for tr in items:
            merged = False
            for k in kept:
                iou = _bbox_iou(tr['bbox'], k['bbox'])
                cont = _bbox_containment(tr['bbox'], k['bbox'])
                if iou >= self.merge_iou or cont >= self.merge_contain:
                    # Mevcut ID kalsin; raw eslemesini de ona bagla
                    self._id_map[tr['raw_id']] = k['track_id']
                    k['bbox'] = [
                        min(k['bbox'][0], tr['bbox'][0]),
                        min(k['bbox'][1], tr['bbox'][1]),
                        max(k['bbox'][2], tr['bbox'][2]),
                        max(k['bbox'][3], tr['bbox'][3]),
                    ]
                    k['confidence'] = max(k['confidence'], tr['confidence'])
                    merged = True
                    break
            if not merged:
                kept.append({
                    'track_id': tr['track_id'],
                    'raw_id': tr['raw_id'],
                    'bbox': list(tr['bbox']),
                    'confidence': tr['confidence'],
                })
        return kept

    def update(self, detections: list, frame, frame_idx: int = 0, total_frames: int = 0) -> list:
        raw = [(d['bbox'], d['confidence'], d['class']) for d in detections]
        tracks = self.tracker.update_tracks(raw, frame=frame)

        items = []
        active_raw = set()
        for track in tracks:
            if not track.is_confirmed():
                continue
            raw_id = track.track_id
            active_raw.add(raw_id)
            x1, y1, x2, y2 = map(int, track.to_ltrb())
            items.append({
                'raw_id': raw_id,
                'track_id': self._display_id(raw_id),
                'bbox': [x1, y1, x2, y2],
                'confidence': round(float(track.det_conf or 0.0), 3),
            })

        before = len(items)
        items = self._merge_overlaps(items)
        if before != len(items):
            logger.info(f"Ust uste kutu birlesti: {before} -> {len(items)}")

        # Olmeyen raw id eslemelerini temizle (DeepSORT track dustu)
        for rid in list(self._id_map.keys()):
            if rid not in active_raw:
                # Birlestirmede baska raw ayni display'e bagli olabilir; raw yoksa sil
                del self._id_map[rid]

        return [
            {
                'track_id': it['track_id'],
                'raw_track_id': it['raw_id'],
                'bbox': it['bbox'],
                'confidence': it['confidence'],
                'class': 'person',
                'is_confirmed': True,
            }
            for it in items
        ]
