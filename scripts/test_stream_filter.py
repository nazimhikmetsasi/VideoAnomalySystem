#!/usr/bin/env python3
"""Sliding window filtresini Kafka olmadan test eder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from streaming.sliding_window import SlidingWindowFilter
import streaming.sliding_window as sw


def main():
    old_min = sw.MIN_EVENTS
    sw.MIN_EVENTS = 2
    filt = SlidingWindowFilter()

    base = {
        'camera_id': 'cam_01',
        'track_id': 7,
        'anomaly_type': 'RUN',
        'confidence_score': 0.88,
    }

    r1 = filt.process({**base, 'timestamp': 1000.0})
    r2 = filt.process({**base, 'timestamp': 1003.0})

    sw.MIN_EVENTS = old_min

    print('=== Sliding Window Test ===')
    print(f'MIN_EVENTS=2 | ilk olay: {"dogrulandi" if r1 else "beklemede"}')
    print(f'ikinci olay: {"dogrulandi" if r2 else "beklemede"}')

    if r1 is None and r2 is not None and r2.get('verified'):
        print('SONUC: OK')
        return 0
    print('SONUC: HATA')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
