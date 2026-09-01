from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from host.eegstream.session import SessionReader
from inference.features.extract import feature_vector

QUALITY_REJECT = 0.7


@dataclass
class StateVector:
    features: Dict[str, float]
    baseline_delta: Dict[str, float]
    confidence: float
    timestamp: str
    valid: bool
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "features": self.features,
            "baseline_delta": self.baseline_delta,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "valid": self.valid,
            "notes": self.notes,
        }

    def format_text(self) -> str:
        lines = ["STATE"]
        if not self.valid:
            lines.append("NO VALID INFERENCE")
        for key in (
            "delta_power",
            "theta_power",
            "alpha_power",
            "beta_power",
            "gamma_power",
            "spectral_entropy",
            "variance",
            "artifact_probability",
        ):
            if key in self.features:
                lines.append(f"{key}: {self.features[key]:.6g}")
        lines.append(f"confidence: {self.confidence:.3f}")
        if self.baseline_delta:
            lines.append("baseline_delta:")
            for k, v in self.baseline_delta.items():
                lines.append(f"  {k}: {v:+.3%}")
        for note in self.notes:
            lines.append(note)
        return "\n".join(lines)


def analyze_channels(
    channels: List[List[float]],
    sample_rate: float,
    *,
    baseline: Optional[Dict[str, float]] = None,
    timestamp: str = "",
) -> StateVector:
    if not channels or not channels[0]:
        return StateVector(
            features={},
            baseline_delta={},
            confidence=0.0,
            timestamp=timestamp,
            valid=False,
            notes=["empty session"],
        )
    feats = feature_vector(channels[0], sample_rate)
    artifact = feats["artifact_probability"]
    valid = artifact < QUALITY_REJECT
    confidence = max(0.0, 1.0 - artifact)
    delta: Dict[str, float] = {}
    if baseline:
        for key, current in feats.items():
            base = baseline.get(key)
            if base is None or base == 0:
                continue
            delta[key] = (current - base) / abs(base)
    notes = []
    if not valid:
        notes.append(f"artifact_probability = {artifact:.2f}")
    return StateVector(
        features=feats,
        baseline_delta=delta,
        confidence=confidence,
        timestamp=timestamp,
        valid=valid,
        notes=notes,
    )


def analyze_session(
    session: SessionReader,
    baseline: Optional[Dict[str, float]] = None,
) -> StateVector:
    return analyze_channels(
        session.channels(),
        session.header.sample_rate,
        baseline=baseline,
        timestamp=session.header.created_at,
    )
