import pytest
from core.kinematics import KinematicsEngine
from core.analyzer import AnomalyAnalyzer
from core.motion_classifier import MotionClassifier, MOTION_RUNNING, MOTION_WALKING, MOTION_STANDING
from core.track_state import TrackStateManager


def test_kinematics_vertical_velocity():
    engine = KinematicsEngine()
    engine.window_size = 5

    m1 = engine.update(1, {'x': 100, 'y': 200, 'z': 0}, 80, 0.0)
    assert m1['sample_count'] == 1

    m2 = engine.update(1, {'x': 100, 'y': 250, 'z': 0}, 75, 0.033)
    assert m2['vertical_velocity'] > 0
    assert m2['horizontal_velocity'] == 0


def test_kinematics_reset_track():
    engine = KinematicsEngine()
    engine.update(1, {'x': 100, 'y': 200, 'z': 0}, 80, 0.0)
    engine.reset_track(1)
    assert 1 not in engine._buffers


def test_analyzer_fall_detection():
    analyzer = AnomalyAnalyzer()
    metrics = {
        'vertical_velocity': 150,
        'horizontal_velocity': 5,
        'spine_angle': 20,
        'sample_count': 10
    }
    event = analyzer.analyze(
        track_id=1,
        metrics=metrics,
        hip_center={'x': 320, 'y': 240, 'z': 0},
        camera_id='cam_test'
    )
    assert event is not None
    assert event['anomaly_type'] == 'FALL'


def test_analyzer_run_detection():
    analyzer = AnomalyAnalyzer()
    metrics = {
        'vertical_velocity': 10,
        'horizontal_velocity': 120,
        'spine_angle': 80,
        'sample_count': 10
    }
    event = analyzer.analyze(
        track_id=2,
        metrics=metrics,
        hip_center={'x': 50, 'y': 50, 'z': 0},
        camera_id='cam_no_zone'
    )
    assert event is not None
    assert event['anomaly_type'] == 'RUN'


def test_motion_classifier_running():
    clf = MotionClassifier()
    clf.confirm_frames = 1
    metrics = {
        'horizontal_velocity': 120,
        'vertical_velocity': 0,
        'spine_angle': 85,
        'sample_count': 10,
    }
    result = clf.classify(1, metrics, None)
    assert result['motion'] == MOTION_RUNNING
    assert result['motion_confirmed'] == MOTION_RUNNING


def test_motion_classifier_walking():
    clf = MotionClassifier()
    clf.confirm_frames = 1
    metrics = {
        'horizontal_velocity': 25,
        'vertical_velocity': 0,
        'spine_angle': 85,
        'sample_count': 10,
    }
    result = clf.classify(2, metrics, None)
    assert result['motion'] == MOTION_WALKING


def test_motion_classifier_standing():
    clf = MotionClassifier()
    clf.confirm_frames = 1
    metrics = {
        'horizontal_velocity': 2,
        'vertical_velocity': 0,
        'spine_angle': 88,
        'sample_count': 10,
    }
    result = clf.classify(3, metrics, None)
    assert result['motion'] == MOTION_STANDING


def test_track_state_jump_detection():
    mgr = TrackStateManager()
    mgr.max_jump_px = 50
    s1 = mgr.update(1, [100, 100, 200, 300])
    assert s1['id_jump'] is False
    s2 = mgr.update(1, [400, 100, 500, 300])
    assert s2['id_jump'] is True


def test_sliding_window_filter():
    from streaming.sliding_window import SlidingWindowFilter
    import streaming.sliding_window as sw
    old_min = sw.MIN_EVENTS
    sw.MIN_EVENTS = 2
    filt = SlidingWindowFilter()
    event = {
        'camera_id': 'cam_01',
        'track_id': 1,
        'anomaly_type': 'FALL',
        'confidence_score': 0.9,
        'timestamp': 1000.0
    }
    assert filt.process(event) is None
    event2 = {**event, 'timestamp': 1002.0}
    verified = filt.process(event2)
    sw.MIN_EVENTS = old_min
    assert verified is not None
    assert verified.get('verified') is True
