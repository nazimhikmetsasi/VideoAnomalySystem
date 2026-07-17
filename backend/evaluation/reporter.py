"""Pilot degerlendirme raporu yazici."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


def write_report(output_dir: Path, summary: dict, video_rows: list[dict]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / 'summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    csv_path = output_dir / 'per_video.csv'
    if video_rows:
        fields = list(video_rows[0].keys())
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(video_rows)

    txt_path = output_dir / 'PILOT_REPORT.txt'
    lines = [
        'MCBU Video Anomaly System — Pilot Degerlendirme Raporu',
        '=' * 56,
        f"Tarih: {summary.get('generated_at', datetime.now().isoformat())}",
        '',
        'OZET METRIKLER',
        f"  Degerlendirilen video : {summary.get('anomaly', {}).get('videos_evaluated', 0)}",
        f"  Precision             : {summary.get('anomaly', {}).get('precision')}",
        f"  Recall                : {summary.get('anomaly', {}).get('recall')}",
        f"  F1                    : {summary.get('anomaly', {}).get('f1')}",
        f"  Accuracy              : {summary.get('anomaly', {}).get('accuracy')}",
        f"  Ort. FAR              : {summary.get('anomaly', {}).get('avg_far')}",
        f"  Ort. kare gecikmesi   : {summary.get('anomaly', {}).get('avg_frame_latency_ms')} ms",
        '',
        'TESPIT (YOLO)',
        f"  mAP@0.5               : {(summary.get('detection') or {}).get('map50')}",
        f"  mAP@0.5:0.95          : {(summary.get('detection') or {}).get('map50_95')}",
        f"  Kaynak                : {(summary.get('detection') or {}).get('source')}",
        '',
        'VIDEO DETAYLARI',
    ]
    for row in video_rows:
        lines.append(
            f"  - {row.get('video')}: status={row.get('status')} | "
            f"TP={row.get('tp')} FP={row.get('fp')} FN={row.get('fn')} | "
            f"latency={row.get('avg_frame_latency_ms')}ms"
        )
    if (summary.get('detection') or {}).get('note'):
        lines.extend(['', 'NOT:', summary['detection']['note']])

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    latest = output_dir.parent / 'latest.json'
    with open(latest, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary_path
