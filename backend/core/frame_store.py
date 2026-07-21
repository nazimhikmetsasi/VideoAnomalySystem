"""Canli kare ve anomali anlik goruntuleri (panel icin)."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import cv2

logger = logging.getLogger('video_pipeline')

ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / 'data' / 'live'
SNAP_DIR = ROOT / 'data' / 'snapshots'


def _ensure_dirs():
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    SNAP_DIR.mkdir(parents=True, exist_ok=True)


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
        # Eski anliklari temizle (son 80)
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


def live_path(camera_id: str) -> Path | None:
    p = LIVE_DIR / f'{camera_id}.jpg'
    return p if p.is_file() else None


def snapshot_path(snapshot_id: str) -> Path | None:
    if not snapshot_id or '/' in snapshot_id or '\\' in snapshot_id or '..' in snapshot_id:
        return None
    p = SNAP_DIR / f'{snapshot_id}.jpg'
    return p if p.is_file() else None
