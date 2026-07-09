"""Kare isleme suresi istatistikleri."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LatencyTracker:
    detect: list[float] = field(default_factory=list)
    track: list[float] = field(default_factory=list)
    pose: list[float] = field(default_factory=list)
    analyze: list[float] = field(default_factory=list)
    total: list[float] = field(default_factory=list)

    def record(self, stage: str, ms: float):
        bucket = getattr(self, stage, None)
        if bucket is not None:
            bucket.append(ms)

    def summary(self) -> dict:
        def stats(values: list[float]) -> dict | None:
            if not values:
                return None
            ordered = sorted(values)
            n = len(ordered)
            p95_idx = min(n - 1, int(n * 0.95))
            return {
                'count': n,
                'avg_ms': round(sum(ordered) / n, 2),
                'p50_ms': round(ordered[n // 2], 2),
                'p95_ms': round(ordered[p95_idx], 2),
                'max_ms': round(ordered[-1], 2),
            }

        return {
            'detect': stats(self.detect),
            'track': stats(self.track),
            'pose': stats(self.pose),
            'analyze': stats(self.analyze),
            'total_frame': stats(self.total),
        }
