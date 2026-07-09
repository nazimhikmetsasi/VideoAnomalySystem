"""Pilot degerlendirme metrikleri."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroundTruthEvent:
    anomaly_type: str
    start_sec: float
    end_sec: float


@dataclass
class PredictedEvent:
    anomaly_type: str
    time_sec: float
    confidence: float = 0.0
    track_id: int | None = None


def _in_window(time_sec: float, event: GroundTruthEvent) -> bool:
    return event.start_sec <= time_sec <= event.end_sec


def match_events(
    ground_truth: list[GroundTruthEvent],
    predictions: list[PredictedEvent],
    tolerance_sec: float = 1.5,
) -> dict:
    """Eslestirme: tahmin, GT penceresi +- tolerans icinde ve ayni tip ise TP."""
    gt_used: set[int] = set()
    pred_used: set[int] = set()
    tp_details: list[dict] = []

    for pi, pred in enumerate(predictions):
        for gi, gt in enumerate(ground_truth):
            if gi in gt_used:
                continue
            if pred.anomaly_type != gt.anomaly_type:
                continue
            window_start = gt.start_sec - tolerance_sec
            window_end = gt.end_sec + tolerance_sec
            if window_start <= pred.time_sec <= window_end:
                gt_used.add(gi)
                pred_used.add(pi)
                tp_details.append({
                    'predicted': pred.anomaly_type,
                    'predicted_sec': pred.time_sec,
                    'ground_truth_sec': (gt.start_sec + gt.end_sec) / 2,
                    'delta_sec': abs(pred.time_sec - (gt.start_sec + gt.end_sec) / 2),
                })
                break

    tp = len(tp_details)
    fp = len(predictions) - tp
    fn = len(ground_truth) - tp

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0

    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'accuracy': round(accuracy, 4),
        'matches': tp_details,
        'false_positive_events': [
            {'type': predictions[i].anomaly_type, 'time_sec': predictions[i].time_sec}
            for i in range(len(predictions)) if i not in pred_used
        ],
        'missed_events': [
            {'type': ground_truth[i].anomaly_type, 'start_sec': ground_truth[i].start_sec}
            for i in range(len(ground_truth)) if i not in gt_used
        ],
    }


def false_alarm_rate(
    predictions: list[PredictedEvent],
    normal_segments: list[tuple[float, float]],
) -> float:
    """NORMAL segmentlerdeki yanlis alarm / toplam normal sure (saniye)."""
    if not normal_segments:
        return 0.0
    normal_seconds = sum(max(0.0, end - start) for start, end in normal_segments)
    if normal_seconds <= 0:
        return 0.0
    false_alarms = 0
    for pred in predictions:
        for start, end in normal_segments:
            if start <= pred.time_sec <= end:
                false_alarms += 1
                break
    return round(false_alarms / normal_seconds, 4)


def aggregate_video_results(video_results: list[dict]) -> dict:
    total_tp = sum(r['tp'] for r in video_results)
    total_fp = sum(r['fp'] for r in video_results)
    total_fn = sum(r['fn'] for r in video_results)
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) else 0.0
    far_values = [r['far'] for r in video_results if r.get('far') is not None]
    latency_values = [r['avg_frame_latency_ms'] for r in video_results if r.get('avg_frame_latency_ms')]

    return {
        'videos_evaluated': len(video_results),
        'tp': total_tp,
        'fp': total_fp,
        'fn': total_fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'accuracy': round(accuracy, 4),
        'avg_far': round(sum(far_values) / len(far_values), 4) if far_values else None,
        'avg_frame_latency_ms': round(sum(latency_values) / len(latency_values), 2) if latency_values else None,
    }
