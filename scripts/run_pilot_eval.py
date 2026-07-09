#!/usr/bin/env python3
"""Pilot degerlendirme calistiricisi — anomali accuracy, latency, mAP."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from config import load_env

load_env()

from evaluation.anomaly_metrics import (
    aggregate_video_results,
    false_alarm_rate,
    match_events,
)
from evaluation.detection_benchmark import run_detection_benchmark
from evaluation.reporter import write_report
from evaluation.video_runner import VideoEvalRunner, annotation_to_events, load_annotation


def find_pilot_pairs(pilot_dir: Path) -> list[tuple[Path, Path]]:
    ann_dir = pilot_dir / 'annotations'
    vid_dir = pilot_dir / 'videos'
    pairs = []
    if not ann_dir.exists():
        return pairs
    for ann_path in sorted(ann_dir.glob('*.json')):
        data = load_annotation(ann_path)
        video_name = data.get('video', ann_path.stem + '.mp4')
        pairs.append((vid_dir / video_name, ann_path))
    return pairs


def main():
    parser = argparse.ArgumentParser(description='MCBU pilot degerlendirme')
    parser.add_argument('--pilot-dir', default=str(ROOT / 'datasets' / 'pilot'))
    parser.add_argument('--output', default=str(ROOT / 'results'))
    parser.add_argument('--tolerance', type=float, default=1.5, help='Eslestirme toleransi (sn)')
    parser.add_argument('--max-frames', type=int, default=None, help='Video basina max kare')
    parser.add_argument('--skip-detection', action='store_true', help='YOLO mAP atla')
    parser.add_argument('--detection-only', action='store_true', help='Sadece mAP calistir')
    args = parser.parse_args()

    pilot_dir = Path(args.pilot_dir)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_dir = Path(args.output) / f'pilot_{timestamp}'

    detection = None
    if not args.detection_only:
        print('=== Anomali pilot degerlendirme ===')
    if not args.skip_detection and not args.detection_only:
        print('YOLO mAP olculuyor...')
        try:
            detection = run_detection_benchmark()
            print(f"  mAP@0.5={detection.get('map50')} | kaynak={detection.get('source')}")
        except Exception as e:
            detection = {'source': 'error', 'error': str(e)}
            print(f"  mAP hatasi: {e}")

    if args.detection_only:
        detection = run_detection_benchmark()
        summary = {'generated_at': datetime.now().isoformat(), 'detection': detection}
        write_report(output_dir, summary, [])
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    pairs = find_pilot_pairs(pilot_dir)
    if not pairs:
        print(f'UYARI: {pilot_dir}/annotations/ icinde JSON bulunamadi.')
        sys.exit(1)

    runner = VideoEvalRunner()
    video_rows = []
    metric_rows = []

    for video_path, ann_path in pairs:
        print(f'Isleniyor: {video_path.name} ...')
        ann = load_annotation(ann_path)
        gt_events, normal_segments = annotation_to_events(ann)
        run_result = runner.run(video_path, max_frames=args.max_frames)

        if run_result['status'] != 'ok':
            video_rows.append({
                'video': run_result['video'],
                'status': run_result['status'],
                'error': run_result.get('error'),
                'tp': 0, 'fp': 0, 'fn': len(gt_events),
                'precision': 0, 'recall': 0, 'accuracy': 0, 'far': None,
                'avg_frame_latency_ms': None,
            })
            print(f"  ATLANDI: {run_result.get('error')}")
            continue

        preds = run_result['predictions']
        metrics = match_events(gt_events, preds, tolerance_sec=args.tolerance)
        far = false_alarm_rate(preds, normal_segments) if normal_segments else None

        row = {
            'video': run_result['video'],
            'status': 'ok',
            'frames': run_result['frames_processed'],
            'fps': run_result['fps'],
            'predictions_count': len(preds),
            'tp': metrics['tp'],
            'fp': metrics['fp'],
            'fn': metrics['fn'],
            'precision': metrics['precision'],
            'recall': metrics['recall'],
            'f1': metrics['f1'],
            'accuracy': metrics['accuracy'],
            'far': far,
            'avg_frame_latency_ms': run_result.get('avg_frame_latency_ms'),
        }
        video_rows.append(row)
        metric_rows.append(row)
        print(
            f"  TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} | "
            f"P={metrics['precision']} R={metrics['recall']} | "
            f"latency={run_result.get('avg_frame_latency_ms')}ms"
        )

    anomaly_summary = aggregate_video_results(metric_rows) if metric_rows else {}
    ok_count = sum(1 for r in video_rows if r.get('status') == 'ok')

    summary = {
        'generated_at': datetime.now().isoformat(),
        'pilot_dir': str(pilot_dir),
        'tolerance_sec': args.tolerance,
        'videos_total': len(video_rows),
        'videos_processed': ok_count,
        'videos_missing': len(video_rows) - ok_count,
        'anomaly': anomaly_summary,
        'detection': detection,
    }

    report_path = write_report(output_dir, summary, video_rows)
    print('')
    print('=== Ozet ===')
    print(json.dumps(anomaly_summary, ensure_ascii=False, indent=2))
    print(f'Rapor: {report_path}')

    if ok_count == 0:
        print('')
        print('Hic video islenmedi. datasets/pilot/videos/ klasorune MP4 ekleyin.')
        print('Ornek: datasets/pilot/videos/normal_01.mp4')
        sys.exit(2)


if __name__ == '__main__':
    main()
