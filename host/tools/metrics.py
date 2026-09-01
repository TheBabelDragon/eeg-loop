from __future__ import annotations

import math
from typing import List, Sequence


def rms(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    return math.sqrt(sum(x * x for x in xs) / len(xs))


def mean(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def variance(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def value_range(xs: Sequence[float]) -> tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    return min(xs), max(xs)


def clipping_fraction(xs: Sequence[float], limit: float) -> float:
    if not xs or limit <= 0:
        return 0.0
    n = sum(1 for x in xs if abs(x) >= limit)
    return n / len(xs)


def duration_hms(n_samples: int, sample_rate: float) -> str:
    if sample_rate <= 0:
        return "00:00:00"
    secs = n_samples / sample_rate
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def channel_report(name: str, xs: Sequence[float], clip_limit: float = 1e6) -> List[str]:
    lo, hi = value_range(xs)
    return [
        name,
        f"  samples:      {len(xs)}",
        f"  RMS:          {rms(xs):.6f}",
        f"  range:        {lo:.6f} .. {hi:.6f}",
        f"  DC offset:    {mean(xs):.6f}",
        f"  variance:     {variance(xs):.6f}",
        f"  clipping:     {clipping_fraction(xs, clip_limit):.4f}",
    ]
