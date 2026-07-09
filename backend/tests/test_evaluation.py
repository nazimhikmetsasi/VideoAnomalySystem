import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.anomaly_metrics import (
    GroundTruthEvent,
    PredictedEvent,
    aggregate_video_results,
    false_alarm_rate,
    match_events,
)


def test_match_true_positive():
    gt = [GroundTruthEvent('RUN', 4.0, 7.0)]
    preds = [PredictedEvent('RUN', 5.2, 0.9)]
    m = match_events(gt, preds, tolerance_sec=1.5)
    assert m['tp'] == 1
    assert m['fp'] == 0
    assert m['fn'] == 0
    assert m['precision'] == 1.0


def test_match_false_positive():
    gt = [GroundTruthEvent('RUN', 4.0, 7.0)]
    preds = [PredictedEvent('RUN', 12.0, 0.9)]
    m = match_events(gt, preds, tolerance_sec=1.5)
    assert m['tp'] == 0
    assert m['fp'] == 1
    assert m['fn'] == 1


def test_false_alarm_rate():
    preds = [PredictedEvent('RUN', 2.0, 0.8)]
    normal = [(0.0, 10.0)]
    far = false_alarm_rate(preds, normal)
    assert far == 0.1


def test_aggregate():
    rows = [
        {'tp': 1, 'fp': 0, 'fn': 0, 'avg_frame_latency_ms': 100, 'far': 0.0},
        {'tp': 1, 'fp': 1, 'fn': 0, 'avg_frame_latency_ms': 200, 'far': 0.1},
    ]
    agg = aggregate_video_results(rows)
    assert agg['tp'] == 2
    assert agg['precision'] == round(2 / 3, 4)
    assert agg['avg_frame_latency_ms'] == 150.0
