"""Birden fazla kamera pipeline yoneticisi."""

from __future__ import annotations

import os
import time
import threading

from config import load_env

load_env()

from core.camera_config import load_cameras_config
from core.pipeline import VideoKafkaProducer
from core.logging_config import setup_logging

logger = setup_logging('multi_camera', 'pipeline.log')


class MultiCameraManager:
    def __init__(self):
        self.pipelines: list[VideoKafkaProducer] = []
        self._threads: list[threading.Thread] = []

    def start_all(self):
        cameras = load_cameras_config()
        if not cameras:
            raise RuntimeError('Aktif kamera bulunamadi — config/cameras.json kontrol edin')

        logger.info(f"{len(cameras)} kamera baslatiliyor...")
        for cam in cameras:
            cam_id = cam['id']
            source = cam.get('source', '0')
            if cam.get('input_type') and cam['input_type'] != 'auto':
                os.environ['CAMERA_INPUT_TYPE'] = cam['input_type']

            pipeline = VideoKafkaProducer(
                source=source,
                camera_id=cam_id,
                show_window=cam.get('show_window', True),
            )
            pipeline.start()
            self.pipelines.append(pipeline)
            logger.info(f"Kamera baslatildi | {cam_id} | {cam.get('name', source)}")

        return self

    def wait(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        for p in self.pipelines:
            p.stop()
        logger.info('Tum kameralar durduruldu.')


def main():
    MultiCameraManager().start_all().wait()


if __name__ == '__main__':
    main()
