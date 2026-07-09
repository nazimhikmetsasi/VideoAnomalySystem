import pytest
from core.kinematics import KinematicsEngine
from core.analyzer import AnomalyAnalyzer


def test_kinematics_vertical_velocity():
    engine = KinematicsEngine()
    engine.window_size = 5

    m1 = engine.update(1, {'x': 100, 'y': 200, 'z': 0}, 80, 0.0)
    assert m1['sample_count'] == 1

    m2 = engine.update(1, {'x': 100, 'y': 250, 'z': 0}, 75, 0.033)
    assert m2['vertical_velocity'] > 0
    assert m2['horizontal_velocity'] == 0


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
