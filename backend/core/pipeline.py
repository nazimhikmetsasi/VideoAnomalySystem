import os
import json
import time
import threading
from config import load_env

load_env()

import cv2
from kafka import KafkaProducer
from core.detector import HumanDetector
from core.tracker import PersonTracker
from core.pose import PoseEstimator
from core.kinematics import KinematicsEngine
from core.analyzer import AnomalyAnalyzer
from core.visualizer import draw_tracks, draw_pose, draw_zones, draw_anomaly_alert
from core.notifier import notify_api
from core.logging_config import setup_logging

logger = setup_logging('video_pipeline', 'pipeline.log')


def on_send_success(record_metadata):
    logger.debug(
        f"Mesaj gonderildi -> Topic: {record_metadata.topic} | "
        f"Partition: {record_metadata.partition} | Offset: {record_metadata.offset}"
    )


def on_send_error(exception):
    logger.error(f"Kafka'ya mesaj gonderilemedi: {exception}")


class VideoKafkaProducer:
    def __init__(self, source=None, topic=None, kafka_enabled=None):
        camera_source = source if source is not None else os.getenv('CAMERA_SOURCE', 0)
        self.cap = cv2.VideoCapture(int(camera_source))
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Kamera acilamadi (CAMERA_SOURCE={camera_source}). "
                f".env dosyasinda CAMERA_SOURCE=1 deneyin."
            )

        self.topic = topic or os.getenv('KAFKA_TOPIC', 'video-stream')
        self.anomaly_topic = os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events')
        self.camera_id = os.getenv('CAMERA_ID', 'cam_01')
        self.frame_width = int(os.getenv('FRAME_WIDTH', 640))
        self.frame_height = int(os.getenv('FRAME_HEIGHT', 480))
        self.target_fps = float(os.getenv('TARGET_FPS', 30))

        if kafka_enabled is None:
            kafka_enabled = os.getenv('KAFKA_ENABLED', 'true').lower() == 'true'
        self.kafka_enabled = kafka_enabled

        logger.info("AI modulleri baslatiliyor...")
        self.detector = HumanDetector()
        self.tracker = PersonTracker()
        self.pose_estimator = PoseEstimator()
        self.kinematics = KinematicsEngine()
        self.analyzer = AnomalyAnalyzer()

        self.producer = None
        if self.kafka_enabled:
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[bootstrap_servers],
                    value_serializer=lambda v: v if isinstance(v, bytes) else json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8'),
                    acks='all',
                    retries=3,
                    retry_backoff_ms=500
                )
                logger.info(
                    f"Kafka Producer baslatildi | topic={self.topic} | "
                    f"anomaly={self.anomaly_topic} | kamera={self.camera_id}"
                )
            except Exception as e:
                logger.warning(f"Kafka baglanamadi — API bildirim modu aktif: {e}")
                self.kafka_enabled = False
                self.producer = None
        else:
            logger.warning("Kafka devre disi — sadece yerel kamera testi modu.")

        self.stopped = False
        self._latest_anomaly = None

    def start(self):
        t = threading.Thread(target=self.stream_video, daemon=True)
        t.start()
        logger.info("Video stream thread baslatildi.")
        return self

    def stream_video(self):
        frame_count = 0
        frame_interval = 1.0 / self.target_fps
        zones = self.analyzer.get_zones_for_camera(self.camera_id)

        while not self.stopped:
            loop_start = time.time()
            success, frame = self.cap.read()
            if not success:
                logger.error("Kameradan goruntu okunamadi.")
                break

            frame_count += 1
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))

            # CLAHE
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            frame = cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)

            # YOLO + DeepSORT
            detections = self.detector.detect(frame)
            tracks = self.tracker.update(detections, frame)

            display = frame.copy()
            display = draw_zones(display, zones)
            display = draw_tracks(display, tracks)

            active_ids = set()
            track_payload = []
            ts = time.time()

            for tr in tracks:
                tid = tr['track_id']
                active_ids.add(tid)
                bbox = tr['bbox']

                # Yeni kisi girdi mi?
                presence = self.analyzer.analyze_presence(tid, self.camera_id, bbox)
                if presence:
                    display = draw_anomaly_alert(display, presence)
                    self._publish_anomaly(presence, [])
                    notify_api(presence)

                pose_data = self.pose_estimator.extract(frame, bbox)

                entry = {
                    'track_id': tid,
                    'bbox': bbox,
                    'confidence': tr['confidence']
                }

                anomaly = None
                if pose_data:
                    spine = self.pose_estimator.spine_angle(pose_data['raw_landmarks'])
                    metrics = self.kinematics.update(tid, pose_data['hip_center'], spine, ts)
                    entry['metrics'] = metrics
                    entry['hip_center'] = pose_data['hip_center']
                    display = draw_pose(display, pose_data['raw_landmarks'], bbox)
                    anomaly = self.analyzer.analyze(
                        tid, metrics, pose_data['hip_center'], self.camera_id
                    )
                else:
                    anomaly = self.analyzer.analyze_zone_bbox(tid, bbox, self.camera_id)

                if anomaly:
                    self._latest_anomaly = anomaly
                    display = draw_anomaly_alert(display, anomaly)
                    landmarks = pose_data['landmarks'] if pose_data else []
                    self._publish_anomaly(anomaly, landmarks)
                    notify_api(anomaly, landmarks)

                track_payload.append(entry)

            self.kinematics.clear_stale(active_ids)
            self.analyzer.clear_tracks(active_ids)

            cv2.imshow("MCBU - Anomali Tespit Sistemi", display)
            cv2.waitKey(1)

            if self.kafka_enabled and self.producer:
                _, buffer = cv2.imencode('.jpg', frame)
                headers = [
                    ('camera_id', self.camera_id.encode('utf-8')),
                    ('timestamp', str(ts).encode('utf-8')),
                    ('person_count', str(len(tracks)).encode('utf-8')),
                    ('tracks', json.dumps(track_payload).encode('utf-8'))
                ]
                self.producer.send(
                    self.topic, key=self.camera_id, value=buffer.tobytes(), headers=headers
                ).add_callback(on_send_success).add_errback(on_send_error)

            if frame_count % 100 == 0:
                logger.info(f"{frame_count}. kare | Takip: {len(tracks)} kisi")

            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_interval - elapsed)
            time.sleep(sleep_time)

    def _publish_anomaly(self, anomaly: dict, landmarks: list):
        payload = {**anomaly, 'landmarks': landmarks}
        if not self.kafka_enabled or not self.producer:
            return
        self.producer.send(
            self.anomaly_topic,
            key=self.camera_id,
            value=json.dumps(payload).encode('utf-8')
        ).add_callback(on_send_success).add_errback(on_send_error)

    def stop(self):
        self.stopped = True
        self.cap.release()
        cv2.destroyAllWindows()
        self.pose_estimator.close()
        if self.producer:
            self.producer.flush()
            self.producer.close()
        logger.info("Pipeline durduruldu.")


def main():
    pipeline = VideoKafkaProducer().start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pipeline.stop()


if __name__ == '__main__':
    main()
