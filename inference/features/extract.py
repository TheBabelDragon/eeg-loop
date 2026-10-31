from __future__ import annotations

import math
from typing import Dict, Sequence

from host.tools.metrics import mean, rms, variance

BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}


def _goertzel_power(xs: Sequence[float], sample_rate: float, freq: float) -> float:
    if not xs or sample_rate <= 0:
        return 0.0
    w = 2.0 * math.pi * freq / sample_rate
    coeff = 2.0 * math.cos(w)
    s0 = s1 = s2 = 0.0
    for x in xs:
        s0 = x + coeff * s1 - s2
        s2 = s1
        s1 = s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def _default_steps(lo: float, hi: float) -> int:
    """Band-aware Goertzel density. Alpha gets denser probes for IAF tracking."""
    width = hi - lo
    # ~0.4 Hz spacing on alpha (8–13); coarser on wide bands
    if lo >= 7.5 and hi <= 14.0:
        return max(12, int(round(width / 0.4)))
    if width <= 5.0:
        return 10
    return 6


def band_power(
    xs: Sequence[float],
    sample_rate: float,
    lo: float,
    hi: float,
    steps: int | None = None,
) -> float:
    """Mean Goertzel power over band, normalized by window length N.

    Raw Goertzel magnitude-squared grows with N; dividing by N keeps absolute
    band powers roughly comparable across different packet/window sizes.
    Relative powers (rel_*) already cancel N and remain the preferred metric.

    Default step density is band-aware: alpha uses ~12–16 probes (~0.4 Hz)
    so a narrow individual-alpha peak is less likely to fall between bins.
    Pass steps= explicitly to override.
    """
    if hi <= lo or not xs:
        return 0.0
    if steps is None:
        steps = _default_steps(lo, hi)
    n = len(xs)
    acc = 0.0
    for i in range(steps):
        f = lo + (hi - lo) * (i + 0.5) / steps
        acc += _goertzel_power(xs, sample_rate, f)
    return (acc / steps) / n


def spectral_entropy(powers: Sequence[float]) -> float:
    total = sum(max(p, 0.0) for p in powers)
    if total <= 0:
        return 0.0
    ent = 0.0
    for p in powers:
        if p <= 0:
            continue
        q = p / total
        ent -= q * math.log(q + 1e-12)
    n = len([p for p in powers if p > 0])
    if n <= 1:
        return 0.0
    return ent / math.log(n)


def artifact_probability(xs: Sequence[float]) -> float:
    """Coarse flags only. Not a clinical artifact detector."""
    if not xs:
        return 1.0
    m = mean(xs)
    v = variance(xs)
    peak = max(abs(x) for x in xs)
    rms_v = rms(xs)
    score = 0.0
    if rms_v > 0 and peak / rms_v > 8:
        score += 0.4
    if v > 0 and abs(m) / math.sqrt(v) > 3:
        score += 0.2
    diffs = [abs(xs[i] - xs[i - 1]) for i in range(1, len(xs))]
    if diffs and max(diffs) > 8 * (sum(diffs) / len(diffs) + 1e-9):
        score += 0.3
    return min(1.0, score)


def feature_vector(xs: Sequence[float], sample_rate: float) -> Dict[str, float]:
    powers = {
        name: band_power(xs, sample_rate, lo, hi) for name, (lo, hi) in BANDS.items()
    }
    total = sum(powers.values()) or 1.0
    return {
        "delta_power": powers["delta"],
        "theta_power": powers["theta"],
        "alpha_power": powers["alpha"],
        "beta_power": powers["beta"],
        "gamma_power": powers["gamma"],
        "rel_delta": powers["delta"] / total,
        "rel_theta": powers["theta"] / total,
        "rel_alpha": powers["alpha"] / total,
        "rel_beta": powers["beta"] / total,
        "rel_gamma": powers["gamma"] / total,
        "spectral_entropy": spectral_entropy(list(powers.values())),
        "variance": variance(xs),
        "rms": rms(xs),
        "artifact_probability": artifact_probability(xs),
    }
