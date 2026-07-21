"""Canli kare, anomali anliklari ve net varlik galerisi (panel icin)."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import cv2

logger = logging.getLogger('video_pipeline')

ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / 'data' / 'live'
SNAP_DIR = ROOT / 'data' / 'snapshots'
GALLERY_DIR = ROOT / 'data' / 'gallery'

# track_id -> last save time (process-local throttle)
_gallery_last: dict[str, float] = {}


def _ensure_dirs():
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)


def save_live_frame(camera_id: str, frame, every_n: int = 5, frame_idx: int = 0) -> None:
    """Panel onizlemesi icin kucuk/dusuk kaliteli kare yazar (CPU dostu)."""
    if every_n > 1 and frame_idx % every_n != 0:
        return
    try:
        _ensure_dirs()
        path = LIVE_DIR / f'{camera_id}.jpg'
        tmp = LIVE_DIR / f'{camera_id}.tmp.jpg'
        h, w = frame.shape[:2]
        max_w = int(os.getenv('LIVE_PREVIEW_MAX_W', 640))
        if w > max_w:
            scale = max_w / float(w)
            frame = cv2.resize(frame, (max_w, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        quality = int(os.getenv('LIVE_PREVIEW_JPEG_Q', 50))
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return
        tmp.write_bytes(buf.tobytes())
        tmp.replace(path)
    except Exception as e:
        logger.debug(f"Canli kare yazilamadi: {e}")


def save_alert_snapshot(camera_id: str, frame, track_id: int | None = None) -> str | None:
    """Anomali anindaki kareyi kaydeder; panelde tiklaninca gosterilir."""
    try:
        _ensure_dirs()
        key = f'{camera_id}_{int(time.time() * 1000)}_{track_id or 0}'
        path = SNAP_DIR / f'{key}.jpg'
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return None
        path.write_bytes(buf.tobytes())
        snaps = sorted(SNAP_DIR.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in snaps[80:]:
            try:
                old.unlink()
            except OSError:
                pass
        return key
    except Exception as e:
        logger.warning(f"Anlik goruntu yazilamadi: {e}")
        return None


def _bbox_clear(bbox: list, frame_shape, conf: float) -> bool:
    """Varlik net mi: yeterli boyut, cerceve ici, guven esigi."""
    if not bbox or len(bbox) < 4:
        return False
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    bw = max(0.0, x2 - x1)
    bh = max(0.0, y2 - y1)
    if bw < 28 or bh < 48:
        return False
    area_ratio = (bw * bh) / max(1.0, float(w * h))
    if area_ratio < 0.008 or area_ratio > 0.55:
        return False
    margin = 4
    if x1 < -margin or y1 < -margin or x2 > w + margin or y2 > h + margin:
        return False
    min_conf = float(os.getenv('GALLERY_MIN_CONF', 0.25))
    if conf < min_conf:
        return False
    return True


def maybe_save_entity_gallery(
    camera_id: str,
    frame,
    tracks: list,
    motion_map: dict | None = None,
    frame_idx: int = 0,
) -> list[str]:
    """Net gorunen varliklar icin panel galerisine kare kaydeder."""
    if not tracks:
        return []
    every = int(os.getenv('GALLERY_EVERY_N', 8))
    if every > 1 and frame_idx % every != 0:
        return []

    cooldown = float(os.getenv('GALLERY_COOLDOWN_SEC', 2.5))
    max_keep = int(os.getenv('GALLERY_MAX_KEEP', 40))
    saved: list[str] = []
    now = time.time()
    motion_map = motion_map or {}

    try:
        _ensure_dirs()
        for tr in tracks:
            tid = tr.get('track_id')
            bbox = tr.get('bbox')
            conf = float(tr.get('confidence') or 0)
            if tid is None or not _bbox_clear(bbox, frame.shape, conf):
                continue
            if tr.get('is_stable') is False:
                continue

            key_throttle = f'{camera_id}:{tid}'
            last = _gallery_last.get(key_throttle, 0.0)
            if now - last < cooldown:
                continue

            gid = f'{camera_id}_{tid}_{int(now * 1000)}'
            jpg = GALLERY_DIR / f'{gid}.jpg'
            meta_path = GALLERY_DIR / f'{gid}.json'

            ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
            if not ok:
                continue
            jpg.write_bytes(buf.tobytes())

            motion = motion_map.get(tid) or {}
            meta = {
                'id': gid,
                'camera_id': camera_id,
                'track_id': tid,
                'timestamp': now,
                'confidence': round(conf, 3),
                'motion': motion.get('confirmed') or motion.get('instant'),
                'bbox': [float(x) for x in bbox[:4]],
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
            _gallery_last[key_throttle] = now
            saved.append(gid)

        metas = sorted(GALLERY_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in metas[max_keep:]:
            try:
                old.unlink(missing_ok=True)
                old.with_suffix('.jpg').unlink(missing_ok=True)
            except OSError:
                pass
    except Exception as e:
        logger.debug(f"Galeri kaydi yazilamadi: {e}")

    return saved


def live_path(camera_id: str) -> Path | None:
    p = LIVE_DIR / f'{camera_id}.jpg'
    return p if p.is_file() else None


def snapshot_path(snapshot_id: str) -> Path | None:
    if not snapshot_id or '/' in snapshot_id or '\\' in snapshot_id or '..' in snapshot_id:
        return None
    p = SNAP_DIR / f'{snapshot_id}.jpg'
    return p if p.is_file() else None


def gallery_path(gallery_id: str) -> Path | None:
    if not gallery_id or '/' in gallery_id or '\\' in gallery_id or '..' in gallery_id:
        return None
    p = GALLERY_DIR / f'{gallery_id}.jpg'
    return p if p.is_file() else None


def list_gallery(camera_id: str | None = None, limit: int = 40) -> list[dict]:
    _ensure_dirs()
    items: list[dict] = []
    for meta_path in sorted(GALLERY_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if camera_id and data.get('camera_id') != camera_id:
            continue
        gid = data.get('id') or meta_path.stem
        if not gallery_path(gid):
            continue
        items.append({
            'id': gid,
            'camera_id': data.get('camera_id'),
            'track_id': data.get('track_id'),
            'timestamp': data.get('timestamp'),
            'confidence': data.get('confidence'),
            'motion': data.get('motion'),
        })
        if len(items) >= limit:
            break
    return items
