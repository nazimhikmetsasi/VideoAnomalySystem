import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.video_source import resolve_camera_source


def test_webcam_index():
    assert resolve_camera_source('0') == 0
    assert resolve_camera_source(1) == 1


def test_rtsp_url():
    url = 'rtsp://192.168.1.100:554/stream1'
    assert resolve_camera_source(url) == url


def test_video_file():
    path = 'datasets/pilot/videos/run_01.mp4'
    assert resolve_camera_source(path) == path


def test_explicit_webcam_type(monkeypatch):
    monkeypatch.setenv('CAMERA_INPUT_TYPE', 'webcam')
    assert resolve_camera_source('1') == 1
