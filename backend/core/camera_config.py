"""Coklu kamera yapilandirmasi."""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_cameras_config() -> list[dict]:
    path = os.getenv('CAMERAS_CONFIG_PATH', 'config/cameras.json')
    if not os.path.isabs(path):
        root = Path(__file__).resolve().parents[2]
        path = os.path.normpath(os.path.join(root, path))

    if not os.path.exists(path):
        return [{
            'id': os.getenv('CAMERA_ID', 'cam_01'),
            'source': os.getenv('CAMERA_SOURCE', '0'),
            'input_type': os.getenv('CAMERA_INPUT_TYPE', 'auto'),
            'enabled': True,
            'name': 'Varsayilan Kamera',
        }]

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    cameras = [c for c in data.get('cameras', []) if c.get('enabled', True)]
    return cameras
