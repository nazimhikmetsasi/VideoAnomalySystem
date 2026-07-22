"""Kur / Birak (Evde / Koruma) — paylasilan alarm politikasi.

Pipeline ve API ayri process oldugu icin durum dosyada tutulur.
  home  = Evde  → tespit devam, bildirim/ses/push yok
  away  = Koruma → normal alarm
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger('api')

VALID_MODES = ('home', 'away')
MODE_LABELS = {
    'home': 'Evde',
    'away': 'Koruma',
}

_ROOT = Path(__file__).resolve().parents[2]
_lock = threading.Lock()
_cache_mode = 'away'
_cache_mtime = 0.0
_cache_checked = 0.0
_CACHE_TTL = 0.4


def _default_path() -> Path:
    raw = os.getenv('SECURITY_MODE_PATH', 'config/security_mode.json')
    path = Path(raw)
    if not path.is_absolute():
        path = _ROOT / path
    return path


def mode_path() -> Path:
    return _default_path()


def _read_file(path: Path) -> dict:
    if not path.exists():
        return {'mode': 'away'}
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {'mode': 'away'}
        return data
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"security_mode okunamadi: {e}")
        return {'mode': 'away'}


def get_mode(force: bool = False) -> str:
    """Guncel mod (kisa TTL onbellek — pipeline hot path)."""
    global _cache_mode, _cache_mtime, _cache_checked
    now = time.time()
    if not force and (now - _cache_checked) < _CACHE_TTL:
        return _cache_mode

    path = mode_path()
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        mtime = 0.0

    with _lock:
        _cache_checked = now
        if not force and mtime == _cache_mtime and _cache_checked:
            return _cache_mode
        data = _read_file(path)
        mode = str(data.get('mode') or 'away').lower().strip()
        if mode not in VALID_MODES:
            mode = 'away'
        _cache_mode = mode
        _cache_mtime = mtime
        return _cache_mode


def is_armed() -> bool:
    """Koruma (away) acik mi?"""
    return get_mode() == 'away'


def get_status() -> dict:
    path = mode_path()
    data = _read_file(path)
    mode = get_mode(force=True)
    return {
        'mode': mode,
        'armed': mode == 'away',
        'label': MODE_LABELS.get(mode, mode),
        'updated_at': data.get('updated_at'),
        'updated_by': data.get('updated_by'),
        'path': str(path),
    }


def set_mode(mode: str, updated_by: str | None = None) -> dict:
    mode = str(mode or '').lower().strip()
    if mode not in VALID_MODES:
        raise ValueError(f"Gecersiz mod: {mode} (home|away)")

    path = mode_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'mode': mode,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'updated_by': updated_by,
    }
    with _lock:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        global _cache_mode, _cache_mtime, _cache_checked
        _cache_mode = mode
        try:
            _cache_mtime = path.stat().st_mtime
        except OSError:
            _cache_mtime = time.time()
        _cache_checked = time.time()

    logger.info(f"Guvenlik modu → {mode} ({MODE_LABELS[mode]}) by={updated_by}")
    return get_status()
