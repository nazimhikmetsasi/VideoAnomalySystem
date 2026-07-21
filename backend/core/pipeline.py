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
from core.track_state import TrackStateManager
from core.visualizer import (
    draw_tracks, draw_pose, draw_zones, draw_anomaly_alert, draw_kinematics_debug
)
from core.notifier import notify_api
from core.logging_config import setup_logging
from core.video_source import open_video_capture, describe_source
from core.frame_store import save_live_frame, save_alert_snapshot

logger = setup_logging('video_pipeline', 'pipeline.log')


def on_send_success(record_metadata):
    logger.debug(
        f"Mesaj gonderildi -> Topic: {record_metadata.topic} | "
        f"Partition: {record_metadata.partition} | Offset: {record_metadata.offset}"
    )


def on_send_error(exception):
    logger.error(f"Kafka'ya mesaj gonderilemedi: {exception}")


class VideoKafkaProducer:
    def __init__(self, source=None, camera_id=None, topic=None, kafka_enabled=None, show_window=True):
        camera_source = source if source is not None else os.getenv('CAMERA_SOURCE', 0)
        self.cap, self._source_desc = open_video_capture(camera_source)
        if not self.cap.isOpened():
            resolved = self._source_desc
            raise RuntimeError(
                f"Video kaynagi acilamadi ({describe_source(resolved)}). "
                f"Webcam: CAMERA_SOURCE=0 | RTSP: rtsp://ip:554/stream"
            )
        logger.info(f"Video kaynagi: {describe_source(self._source_desc)}")

        self.topic = topic or os.getenv('KAFKA_TOPIC', 'video-stream')
        self.anomaly_topic = os.getenv('KAFKA_ANOMALY_TOPIC', 'anomaly-events')
        self.camera_id = camera_id or os.getenv('CAMERA_ID', 'cam_01')
        self.window_title = f"MCBU - {self.camera_id}"
        self.show_window = show_window
        self.debug_kinematics = os.getenv('DEBUG_KINEMATICS', 'true').lower() == 'true'
        self.frame_width = int(os.getenv('FRAME_WIDTH', 640))
        self.frame_height = int(os.getenv('FRAME_HEIGHT', 480))
        self.target_fps = float(os.getenv('TARGET_FPS', 30))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if kafka_enabled is None:
            kafka_enabled = os.getenv('KAFKA_ENABLED', 'true').lower() == 'true'
        self.kafka_enabled = kafka_enabled

        logger.info("AI modulleri baslatiliyor...")
        self.detector = HumanDetector()
        self.tracker = PersonTracker(video_source=self._source_desc)
        self.pose_estimator = PoseEstimator()
        self.kinematics = KinematicsEngine()
        self.analyzer = AnomalyAnalyzer()
        self.track_state = TrackStateManager()

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
            try:
                detections = self.detector.detect(frame)
                tracks = self.tracker.update(
                    detections,
                    frame,
                    frame_idx=frame_count,
                    total_frames=self.total_frames,
                )
            except Exception as e:
                logger.exception(f"Takip hatasi (kare={frame_count}): {e}")
                continue
            frame_poses = self.pose_estimator.extract_all(frame)

            display = frame.copy()
            display = draw_zones(display, zones)

            active_ids = set()
            track_payload = []
            motion_map = {}
            ts = time.time()

            for tr in tracks:
                tid = tr['track_id']
                active_ids.add(tid)
                bbox = tr['bbox']

                state = self.track_state.update(tid, bbox)
                tr['is_stable'] = state['is_stable']
                if state['id_jump']:
                    # Sadece kinematik sifirla — hareket etiketi/cooldown silinmesin (Belirsiz olmasin)
                    self.kinematics.reset_track(tid)

                # Yeni kisi girdi mi?
                presence = self.analyzer.analyze_presence(tid, self.camera_id, bbox)
                if presence:
                    display = draw_anomaly_alert(display, presence)
                    self._publish_anomaly(presence, [])
                    notify_api(presence)

                pose_data = self.pose_estimator.match_track(bbox, frame_poses)

                entry = {
                    'track_id': tid,
                    'bbox': bbox,
                    'confidence': tr['confidence']
                }

                anomaly = None
                if pose_data and state['is_stable']:
                    spine = self.pose_estimator.spine_angle(pose_data['raw_landmarks'])
                    metrics = self.kinematics.update(tid, pose_data['hip_center'], spine, ts)
                    entry['metrics'] = metrics
                    entry['hip_center'] = pose_data['hip_center']
                    display = draw_pose(display, pose_data['raw_landmarks'], bbox)
                    if self.debug_kinematics:
                        display = draw_kinematics_debug(
                            display, tid, metrics,
                            self.analyzer.run_speed, self.analyzer.fall_vy,
                            y_offset=55 + len(track_payload) * 70,
                        )
                    pose_features = pose_data.get('features')
                    motion_preview = self.analyzer.motion_classifier.classify(tid, metrics, pose_features)
                    metrics.update(motion_preview)
                    motion_map[tid] = motion_preview
                    anomaly = self.analyzer.analyze(
                        tid, metrics, pose_data['hip_center'], self.camera_id,
                        pose_features, motion_preview,
                    )
                elif pose_data:
                    spine = self.pose_estimator.spine_angle(pose_data['raw_landmarks'])
                    metrics = self.kinematics.update(tid, pose_data['hip_center'], spine, ts)
                    pose_features = pose_data.get('features')
                    motion_preview = self.analyzer.motion_classifier.classify(tid, metrics, pose_features)
                    motion_map[tid] = motion_preview
                    display = draw_pose(display, pose_data['raw_landmarks'], bbox)
                else:
                    # Pose eslesmedi — bbox merkezi ile hareket tahmini (Belirsiz kalmasin)
                    cx = (bbox[0] + bbox[2]) / 2.0
                    cy = (bbox[1] + bbox[3]) / 2.0
                    hip = {'x': cx, 'y': cy, 'z': 0.0}
                    metrics = self.kinematics.update(tid, hip, 85.0, ts)
                    motion_preview = self.analyzer.motion_classifier.classify(tid, metrics, None)
                    metrics.update(motion_preview)
                    motion_map[tid] = motion_preview
                    entry['metrics'] = metrics
                    entry['hip_center'] = hip
                    if state['is_stable']:
                        anomaly = self.analyzer.analyze(
                            tid, metrics, hip, self.camera_id, None, motion_preview,
                        )

                if anomaly:
                    self._latest_anomaly = anomaly
                    display = draw_anomaly_alert(display, anomaly)
                    landmarks = pose_data['landmarks'] if pose_data else []
                    snap_id = save_alert_snapshot(self.camera_id, display, anomaly.get('track_id'))
                    if snap_id:
                        anomaly['snapshot_id'] = snap_id
                    # Panel icin dogrudan API; Kafka anomaly cift bildirim uretmesin
                    notify_api(anomaly, landmarks)
                    if os.getenv('ANOMALY_KAFKA_PUBLISH', 'false').lower() == 'true':
                        self._publish_anomaly(anomaly, landmarks)

                track_payload.append(entry)

            display = draw_tracks(display, tracks, motion_map)
            self.kinematics.clear_stale(active_ids)
            self.analyzer.clear_tracks(active_ids)
            self.track_state.clear_stale(active_ids)

            save_live_frame(self.camera_id, display, every_n=5, frame_idx=frame_count)

            if self.show_window:
                cv2.imshow(self.window_title, display)
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
        if self.show_window:
            cv2.destroyWindow(self.window_title)
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
