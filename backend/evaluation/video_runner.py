"""Video dosyasi uzerinde pipeline calistirir — degerlendirme icin."""

from __future__ import annotations

import os
import time
from pathlib import Path

import cv2

from core.detector import HumanDetector
from core.tracker import PersonTracker
from core.pose import PoseEstimator
from core.kinematics import KinematicsEngine
from core.analyzer import AnomalyAnalyzer
from evaluation.anomaly_metrics import GroundTruthEvent, PredictedEvent
from evaluation.latency import LatencyTracker


def _apply_clahe(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)


class VideoEvalRunner:
    def __init__(self, camera_id: str = 'cam_01'):
        self.camera_id = camera_id
        self.frame_width = int(os.getenv('FRAME_WIDTH', 640))
        self.frame_height = int(os.getenv('FRAME_HEIGHT', 480))
        self.detector = HumanDetector()
        self.tracker = PersonTracker()
        self.pose_estimator = PoseEstimator()
        self.kinematics = KinematicsEngine()
        self.analyzer = AnomalyAnalyzer()
        self.latency = LatencyTracker()

    def run(self, video_path: str | Path, max_frames: int | None = None, camera_id: str | None = None) -> dict:
        path = Path(video_path)
        cam_id = camera_id or self.camera_id
        if not path.exists():
            return {
                'video': path.name,
                'status': 'missing',
                'error': f'Video bulunamadi: {path}',
                'predictions': [],
            }

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return {
                'video': path.name,
                'status': 'error',
                'error': f'Video acilamadi: {path}',
                'predictions': [],
            }

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        predictions: list[PredictedEvent] = []
        frame_idx = 0
        # Her videoda temiz takip durumu
        self.kinematics = KinematicsEngine()
        self.tracker = PersonTracker()
        self.analyzer = AnomalyAnalyzer()

        try:
            while True:
                if max_frames is not None and frame_idx >= max_frames:
                    break
                t0 = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    break

                frame_idx += 1
                time_sec = frame_idx / fps
                frame = cv2.resize(frame, (self.frame_width, self.frame_height))
                frame = _apply_clahe(frame)

                t1 = time.perf_counter()
                detections = self.detector.detect(frame)
                t2 = time.perf_counter()
                tracks = self.tracker.update(detections, frame)
                t3 = time.perf_counter()
                frame_poses = self.pose_estimator.extract_all(frame)

                active_ids = set()
                ts = time.time()
                t4 = t3

                for tr in tracks:
                    tid = tr['track_id']
                    active_ids.add(tid)
                    bbox = tr['bbox']

                    presence = self.analyzer.analyze_presence(tid, cam_id, bbox)
                    if presence:
                        predictions.append(PredictedEvent(
                            anomaly_type=presence['anomaly_type'],
                            time_sec=time_sec,
                            confidence=presence['confidence_score'],
                            track_id=tid,
                        ))

                    t_pose_start = time.perf_counter()
                    pose_data = self.pose_estimator.match_track(bbox, frame_poses)
                    t4 = time.perf_counter()

                    anomaly = None
                    if pose_data:
                        spine = self.pose_estimator.spine_angle(pose_data['raw_landmarks'])
                        metrics = self.kinematics.update(tid, pose_data['hip_center'], spine, ts)
                        pose_features = pose_data.get('features')
                        anomaly = self.analyzer.analyze(
                            tid, metrics, pose_data['hip_center'], cam_id,
                            pose_features,
                        )
                    else:
                        anomaly = self.analyzer.analyze_zone_bbox(tid, bbox, cam_id)

                    if anomaly:
                        predictions.append(PredictedEvent(
                            anomaly_type=anomaly['anomaly_type'],
                            time_sec=time_sec,
                            confidence=anomaly['confidence_score'],
                            track_id=tid,
                        ))

                    self.latency.record('pose', (t4 - t_pose_start) * 1000)

                self.kinematics.clear_stale(active_ids)
                self.analyzer.clear_tracks(active_ids)

                t5 = time.perf_counter()
                self.latency.record('detect', (t2 - t1) * 1000)
                self.latency.record('track', (t3 - t2) * 1000)
                self.latency.record('analyze', (t5 - t4) * 1000)
                self.latency.record('total', (t5 - t0) * 1000)

        finally:
            cap.release()

        latency_summary = self.latency.summary()
        avg_total = latency_summary.get('total_frame') or {}
        return {
            'video': path.name,
            'status': 'ok',
            'camera_id': cam_id,
            'fps': round(fps, 2),
            'frames_processed': frame_idx,
            'predictions': predictions,
            'avg_frame_latency_ms': avg_total.get('avg_ms'),
            'latency': latency_summary,
        }


def load_annotation(annotation_path: Path) -> dict:
    import json
    with open(annotation_path, encoding='utf-8') as f:
        return json.load(f)


def annotation_to_events(data: dict) -> tuple[list[GroundTruthEvent], list[tuple[float, float]]]:
    events = [
        GroundTruthEvent(
            anomaly_type=e['type'],
            start_sec=float(e['start_sec']),
            end_sec=float(e['end_sec']),
        )
        for e in data.get('events', [])
        if e.get('type') != 'NORMAL'
    ]
    normal_segments = [
        (float(e['start_sec']), float(e['end_sec']))
        for e in data.get('events', [])
        if e.get('type') == 'NORMAL'
    ]
    return events, normal_segments
