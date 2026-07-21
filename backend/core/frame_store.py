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


def save_alert_snapshot(
    camera_id: str,
    frame,
    track_id: int | None = None,
    meta: dict | None = None,
) -> str | None:
    """Bildirim anindaki kareyi kaydeder (panel alarm galerisi)."""
    try:
        _ensure_dirs()
        key = f'{camera_id}_{int(time.time() * 1000)}_{track_id or 0}'
        path = SNAP_DIR / f'{key}.jpg'
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            return None
        path.write_bytes(buf.tobytes())

        payload = {
            'id': key,
            'camera_id': camera_id,
            'track_id': track_id,
            'timestamp': time.time(),
            'anomaly_type': (meta or {}).get('anomaly_type'),
            'confidence_score': (meta or {}).get('confidence_score'),
            'motion': (meta or {}).get('motion'),
            'report': (meta or {}).get('report'),
        }
        (SNAP_DIR / f'{key}.json').write_text(
            json.dumps(payload, ensure_ascii=False), encoding='utf-8',
        )

        snaps = sorted(SNAP_DIR.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in snaps[80:]:
            try:
                old.unlink(missing_ok=True)
                old.with_suffix('.json').unlink(missing_ok=True)
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


def delete_alert_snapshots(ids: list[str]) -> dict:
    """Secilen alarm anliklarini siler."""
    _ensure_dirs()
    deleted = []
    missing = []
    for raw in ids:
        sid = str(raw or '').strip()
        if not sid or '/' in sid or '\\' in sid or '..' in sid:
            missing.append(sid)
            continue
        jpg = SNAP_DIR / f'{sid}.jpg'
        meta = SNAP_DIR / f'{sid}.json'
        removed = False
        if jpg.is_file():
            try:
                jpg.unlink()
                removed = True
            except OSError:
                pass
        if meta.is_file():
            try:
                meta.unlink()
                removed = True
            except OSError:
                pass
        if removed:
            deleted.append(sid)
        else:
            missing.append(sid)
    return {'deleted': deleted, 'missing': missing, 'count': len(deleted)}


def gallery_path(gallery_id: str) -> Path | None:
    if not gallery_id or '/' in gallery_id or '\\' in gallery_id or '..' in gallery_id:
        return None
    p = GALLERY_DIR / f'{gallery_id}.jpg'
    return p if p.is_file() else None


def _parse_snapshot_stem(stem: str) -> dict:
    """cam_01_1784635329653_11 -> camera_id, timestamp_ms, track_id"""
    parts = stem.rsplit('_', 2)
    if len(parts) == 3 and parts[1].isdigit():
        cam, ts_ms, tid = parts
        return {
            'id': stem,
            'snapshot_id': stem,
            'camera_id': cam,
            'track_id': int(tid) if tid.isdigit() else tid,
            'timestamp': int(ts_ms) / 1000.0 if len(ts_ms) >= 12 else float(ts_ms),
        }
    return {
        'id': stem,
        'snapshot_id': stem,
        'camera_id': None,
        'track_id': None,
        'timestamp': None,
    }


def list_alert_snapshots(camera_id: str | None = None, limit: int = 40) -> list[dict]:
    """Bildirim aninda alinmis ekran goruntuleri (jpg + meta)."""
    _ensure_dirs()
    by_id: dict[str, dict] = {}

    for meta_path in SNAP_DIR.glob('*.json'):
        try:
            data = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        gid = data.get('id') or meta_path.stem
        if not snapshot_path(gid):
            continue
        by_id[gid] = {
            'id': gid,
            'snapshot_id': gid,
            'camera_id': data.get('camera_id'),
            'track_id': data.get('track_id'),
            'timestamp': data.get('timestamp'),
            'anomaly_type': data.get('anomaly_type'),
            'confidence_score': data.get('confidence_score'),
            'motion': data.get('motion'),
            'report': data.get('report'),
        }

    for jpg in SNAP_DIR.glob('*.jpg'):
        stem = jpg.stem
        if stem in by_id:
            continue
        parsed = _parse_snapshot_stem(stem)
        if parsed.get('timestamp') is None:
            parsed['timestamp'] = jpg.stat().st_mtime
        by_id[stem] = parsed

    items = list(by_id.values())
    if camera_id:
        items = [x for x in items if x.get('camera_id') == camera_id]

    def sort_key(x):
        t = x.get('timestamp') or 0
        try:
            return float(t)
        except (TypeError, ValueError):
            return 0.0

    items.sort(key=sort_key, reverse=True)
    return items[:limit]


def list_gallery(camera_id: str | None = None, limit: int = 40) -> list[dict]:
    """Eski net-varlik galerisi (opsiyonel)."""
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
