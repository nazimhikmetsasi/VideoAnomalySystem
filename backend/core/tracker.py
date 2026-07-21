import os
import logging

import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort

from core.reid_gallery import ReIDGallery

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


def _bbox_area(b: list) -> float:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


class PersonTracker:
    """
    DeepSORT takip + gorunum ReID galerisi.

    - Ust uste kutularda union YOK (sisiren kutu engeli)
    - Oturumda ekrandan cikan ID'ye ReID ile geri donulmez
      (sirali uniformali kisiler ayni ID/cooldown'a dusmesin)
    - DeepSORT track hayattayken raw→ID eslemesi korunur (kisa kayip)
    """

    def __init__(self, video_source=None):
        max_age = int(os.getenv('DEEPSORT_MAX_AGE', 50))
        n_init = int(os.getenv('DEEPSORT_N_INIT', 3))
        max_cosine = float(os.getenv('DEEPSORT_MAX_COSINE_DIST', 0.3))
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
        self.gallery = ReIDGallery()
        self._raw_to_id: dict[int, int] = {}
        self._last_seen: dict[int, int] = {}
        self._session_ids: set[int] = set()
        self._last_bbox: dict[int, list] = {}
        self._sid_bbox: dict[int, list] = {}
        self.merge_iou = float(os.getenv('TRACK_MERGE_IOU', 0.55))
        self.merge_contain = float(os.getenv('TRACK_MERGE_CONTAIN', 0.85))
        # Sadece asiri buyuk hayaletler; yakindaki kisi elenmesin
        self.max_area_ratio = float(os.getenv('TRACK_MAX_AREA_RATIO', 0.55))
        self.max_aspect = float(os.getenv('TRACK_MAX_ASPECT', 4.0))
        self.max_stale = int(os.getenv('TRACK_MAX_STALE', 5))
        self.max_grow = float(os.getenv('TRACK_MAX_GROW', 3.0))
        self.soft_reacq_frames = int(os.getenv('REID_SOFT_REACQUIRE', 8))
        self.soft_reacq_dist = float(os.getenv('REID_SOFT_DIST_PX', 70))
        self._frame_idx = 0
        self._frame_area = 1.0

        logger.info(
            f"DeepSORT+ReID | max_age={max_age} | gallery={len(self.gallery._emb)} kisi "
            f"| max_area={self.max_area_ratio}"
        )

    def _is_sane_bbox(self, bbox: list) -> bool:
        x1, y1, x2, y2 = bbox
        w, h = max(0, x2 - x1), max(0, y2 - y1)
        if w < 8 or h < 16:
            return False
        area = w * h
        if area > self._frame_area * self.max_area_ratio:
            return False
        aspect = w / max(h, 1)
        if aspect > self.max_aspect or aspect < 0.15:
            return False
        return True

    def _merge_overlaps(self, items: list) -> list:
        if len(items) <= 1:
            return items
        items = sorted(items, key=lambda x: x['confidence'], reverse=True)
        kept = []
        for tr in items:
            merged = False
            for k in kept:
                iou = _bbox_iou(tr['bbox'], k['bbox'])
                cont = _bbox_containment(tr['bbox'], k['bbox'])
                if iou < self.merge_iou and cont < self.merge_contain:
                    continue
                a1, a2 = _bbox_area(tr['bbox']), _bbox_area(k['bbox'])
                ratio = max(a1, a2) / max(min(a1, a2), 1.0)
                if ratio > 4.0 and iou < 0.7:
                    continue
                k['raw_ids'] = list(k.get('raw_ids') or [k['raw_id']]) + [tr['raw_id']]
                if tr['confidence'] > k['confidence'] or (
                    abs(tr['confidence'] - k['confidence']) < 0.05
                    and a1 < a2
                ):
                    k['bbox'] = tr['bbox']
                    k['feat'] = tr.get('feat') if tr.get('feat') is not None else k.get('feat')
                elif tr.get('feat') is not None and k.get('feat') is None:
                    k['feat'] = tr['feat']
                k['confidence'] = max(k['confidence'], tr['confidence'])
                merged = True
                break
            if not merged:
                row = dict(tr)
                row['raw_ids'] = [tr['raw_id']]
                kept.append(row)
        return kept

    def _blocked_ids(self, busy: set[int]) -> set[int]:
        """
        Bu oturumda gorulup su an ekranda olmayan ID'ler.
        Sirali 2./3. kisi ilk kisinin ID'sine (ve cooldown'una) yapisamaz.
        Video yeniden baslayinca session bos → galeri eslesmesi serbest.
        """
        return {sid for sid in self._session_ids if sid not in busy}

    def _soft_reacquire(self, bbox: list, busy: set[int], blocked: set[int]) -> int | None:
        """Kisa kayip: ayni konumdaki kisiye yeni ID verme (uzak kapidan gelen yeni kisiye verme)."""
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        best = None
        best_dist = 1e9
        for sid in blocked:
            if sid in busy:
                continue
            gap = self._frame_idx - self._last_seen.get(sid, -10**9)
            if gap > self.soft_reacq_frames:
                continue
            prev = self._sid_bbox.get(sid)
            if not prev:
                continue
            px = (prev[0] + prev[2]) / 2.0
            py = (prev[1] + prev[3]) / 2.0
            dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if dist < self.soft_reacq_dist and dist < best_dist:
                best = sid
                best_dist = dist
        return best

    def update(self, detections: list, frame, frame_idx: int = 0, total_frames: int = 0) -> list:
        self._frame_idx = int(frame_idx) if frame_idx else self._frame_idx + 1
        h, w = frame.shape[:2]
        self._frame_area = float(max(h * w, 1))

        raw = []
        for d in detections:
            x1, y1, x2, y2 = d['bbox']
            # deep_sort_realtime [left, top, w, h] ister — xyxy degil
            w = max(1, int(x2) - int(x1))
            h = max(1, int(y2) - int(y1))
            raw.append(([int(x1), int(y1), w, h], float(d['confidence']), d['class']))
        tracks = self.tracker.update_tracks(raw, frame=frame)

        items = []
        alive_raw = set()
        for track in tracks:
            if not track.is_confirmed():
                continue
            raw_id = int(track.track_id)
            # DeepSORT track hayatta → ID eslemesini koru (gostermesek bile)
            alive_raw.add(raw_id)

            stale = int(getattr(track, 'time_since_update', 0) or 0)
            if stale > self.max_stale:
                continue

            x1, y1, x2, y2 = map(int, track.to_ltrb())
            bbox = [x1, y1, x2, y2]
            if not self._is_sane_bbox(bbox):
                logger.debug(f"Asiri buyuk/sacma kutu elendi | raw={raw_id} | {bbox}")
                continue

            prev = self._last_bbox.get(raw_id)
            if prev is not None:
                grow = _bbox_area(bbox) / max(_bbox_area(prev), 1.0)
                # Sadece siniri asan sismeyi engelle; normal yaklasma buyumesine izin ver
                if grow > self.max_grow and _bbox_area(bbox) > self._frame_area * 0.2:
                    bbox = prev
            self._last_bbox[raw_id] = bbox

            feat = track.get_feature()
            feat = np.asarray(feat, dtype=np.float32) if feat is not None else None
            conf = track.det_conf
            if conf is None:
                conf = 0.0
            items.append({
                'raw_id': raw_id,
                'bbox': bbox,
                'confidence': round(float(conf), 3),
                'feat': feat,
            })

        before = len(items)
        items = self._merge_overlaps(items)
        if before != len(items):
            logger.info(f"Ust uste kutu birlesti: {before} -> {len(items)}")

        busy: set[int] = set()
        for it in items:
            for rid in it.get('raw_ids') or [it['raw_id']]:
                if rid in self._raw_to_id:
                    busy.add(self._raw_to_id[rid])
        # Hayatta ama stale olan track'lerin ID'si de busy sayilsin
        for rid, sid in self._raw_to_id.items():
            if rid in alive_raw:
                busy.add(sid)

        blocked = self._blocked_ids(busy)
        tracked = []
        for it in items:
            if not self._is_sane_bbox(it['bbox']):
                continue
            raw_ids = it.get('raw_ids') or [it['raw_id']]
            sid = None
            for rid in raw_ids:
                if rid in self._raw_to_id:
                    sid = self._raw_to_id[rid]
                    break
            if sid is None:
                soft = self._soft_reacquire(it['bbox'], busy, blocked)
                if soft is not None:
                    sid = soft
                    self.gallery.update(sid, it.get('feat'))
                    logger.info(f"ReID soft reacquire | ID={sid}")
                else:
                    sid = self.gallery.alloc(it.get('feat'), busy, blocked)
            else:
                self.gallery.update(sid, it.get('feat'))

            busy.add(sid)
            self._session_ids.add(sid)
            self._last_seen[sid] = self._frame_idx
            self._sid_bbox[sid] = list(it['bbox'])
            for rid in raw_ids:
                self._raw_to_id[rid] = sid

            tracked.append({
                'track_id': sid,
                'raw_track_id': raw_ids[0],
                'bbox': it['bbox'],
                'confidence': it['confidence'],
                'class': 'person',
                'is_confirmed': True,
            })

        for rid in list(self._raw_to_id.keys()):
            if rid not in alive_raw:
                del self._raw_to_id[rid]
        for rid in list(self._last_bbox.keys()):
            if rid not in alive_raw:
                del self._last_bbox[rid]

        return tracked
