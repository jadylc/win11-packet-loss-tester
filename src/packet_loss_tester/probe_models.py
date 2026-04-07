from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(slots=True)
class ProbeResult:
    sequence: int
    sampled_at: datetime
    target: str
    success: bool
    latency_ms: float | None
    status: str
    raw_output: str
    transport: str


@dataclass(slots=True)
class ProbeStats:
    sent: int = 0
    received: int = 0
    lost: int = 0
    loss_rate: float = 0.0
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    avg_latency_ms: float | None = None
    jitter_ms: float | None = None

    @classmethod
    def from_results(cls, results: Iterable[ProbeResult]) -> "ProbeStats":
        items = list(results)
        sent = len(items)
        received = sum(1 for item in items if item.success)
        lost = sent - received
        latencies = [item.latency_ms for item in items if item.success and item.latency_ms is not None]
        jitter = None
        if len(latencies) >= 2:
            diffs = [abs(current - previous) for previous, current in zip(latencies, latencies[1:])]
            jitter = statistics.fmean(diffs)
        return cls(
            sent=sent,
            received=received,
            lost=lost,
            loss_rate=(lost / sent * 100.0) if sent else 0.0,
            min_latency_ms=min(latencies) if latencies else None,
            max_latency_ms=max(latencies) if latencies else None,
            avg_latency_ms=statistics.fmean(latencies) if latencies else None,
            jitter_ms=jitter,
        )
