"""Kamera, RTSP, video dosyasi ve webcam kaynaklarini acar."""

from __future__ import annotations

import os
import cv2

VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.webm')


def resolve_camera_source(source=None) -> str | int:
    raw = source if source is not None else os.getenv('CAMERA_SOURCE', '0')
    input_type = os.getenv('CAMERA_INPUT_TYPE', 'auto').lower().strip()

    if input_type == 'webcam':
        return int(raw)
    if input_type == 'rtsp':
        return str(raw)
    if input_type == 'file':
        return str(raw)

    # auto
    text = str(raw).strip()
    if text.isdigit():
        return int(text)
    lower = text.lower()
    if lower.startswith(('rtsp://', 'rtsps://', 'http://', 'https://')):
        return text
    if lower.endswith(VIDEO_EXTENSIONS):
        return text
    return text


def open_video_capture(source=None) -> tuple[cv2.VideoCapture, str | int]:
    resolved = resolve_camera_source(source)
    cap = cv2.VideoCapture(resolved)

    if isinstance(resolved, str) and resolved.lower().startswith(('rtsp://', 'rtsps://')):
        buffer_size = int(os.getenv('RTSP_BUFFER_SIZE', '1'))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)

    return cap, resolved


def describe_source(resolved: str | int) -> str:
    if isinstance(resolved, int):
        return f'webcam:{resolved}'
    if str(resolved).lower().startswith(('rtsp://', 'rtsps://')):
        return f'rtsp:{resolved}'
    if str(resolved).lower().endswith(VIDEO_EXTENSIONS):
        return f'file:{resolved}'
    return str(resolved)
