"""Immutable EEGStream session I/O with integrity guarantees.

Core rule: raw EEG recordings are immutable evidence. Analysis operates on
derived data only. This module enforces protocol validation, atomic publication,
and independently verifiable finalization metadata.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, TextIO, Tuple, Union

FORMAT = "eeg-loop.session"
VERSION_V1 = 1
VERSION_V2 = 2
SUPPORTED_VERSIONS = {VERSION_V1, VERSION_V2}

# Quality is a coarse on-device hint in [0, 1].
QUALITY_MIN = 0.0
QUALITY_MAX = 1.0


class SessionError(ValueError):
    """Base for session integrity / protocol errors."""


class SessionHeaderError(SessionError):
    """Invalid or unsupported session header."""


class PacketValidationError(SessionError):
    """A packet failed protocol validation."""


class SessionIncompleteError(SessionError):
    """Session is truncated or missing finalization."""


class SessionIntegrityError(SessionError):
    """Integrity digest mismatch or finalization failure."""


@dataclass
class SessionHeader:
    format: str = FORMAT
    version: int = VERSION_V1
    session_id: str = ""
    sample_rate: float = 0.0
    channel_count: int = 0
    channel_names: List[str] = field(default_factory=list)
    units: str = "raw_counts"
    source: str = "unknown"
    created_at: str = ""
    hardware_revision: Optional[str] = None
    firmware_revision: Optional[str] = None
    software_revision: str = "0.1.0-scaffold"

    @classmethod
    def from_dict(cls, data: dict) -> "SessionHeader":
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    def validate(self) -> None:
        if self.format != FORMAT:
            raise SessionHeaderError(f"unknown session format: {self.format!r}")
        if self.version not in SUPPORTED_VERSIONS:
            raise SessionHeaderError(
                f"unsupported session version: {self.version} "
                f"(supported: {sorted(SUPPORTED_VERSIONS)})"
            )
        if not isinstance(self.sample_rate, (int, float)) or not math.isfinite(
            self.sample_rate
        ):
            raise SessionHeaderError(
                f"sample_rate must be finite: {self.sample_rate!r}"
            )
        if self.sample_rate <= 0:
            raise SessionHeaderError(
                f"sample_rate must be > 0: {self.sample_rate}"
            )
        if not isinstance(self.channel_count, int) or self.channel_count < 1:
            raise SessionHeaderError(
                f"channel_count must be a positive integer: {self.channel_count!r}"
            )
        if self.channel_names:
            if len(self.channel_names) != self.channel_count:
                raise SessionHeaderError(
                    f"channel_names length {len(self.channel_names)} "
                    f"!= channel_count {self.channel_count}"
                )
            if len(set(self.channel_names)) != len(self.channel_names):
                raise SessionHeaderError(
                    f"channel_names must be unique: {self.channel_names}"
                )
            for name in self.channel_names:
                if not isinstance(name, str) or not name.strip():
                    raise SessionHeaderError(
                        f"channel name must be nonempty string: {name!r}"
                    )
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise SessionHeaderError(
                f"session_id must be a nonempty string: {self.session_id!r}"
            )
        if not isinstance(self.units, str) or not self.units.strip():
            raise SessionHeaderError(f"units must be a nonempty string: {self.units!r}")
        if not isinstance(self.source, str) or not self.source.strip():
            raise SessionHeaderError(
                f"source must be a nonempty string: {self.source!r}"
            )
        if not isinstance(self.created_at, str) or not self.created_at.strip():
            raise SessionHeaderError(
                f"created_at must be a nonempty string: {self.created_at!r}"
            )
        for field_name in ("hardware_revision", "firmware_revision"):
            val = getattr(self, field_name)
            if val is not None and (
                not isinstance(val, str) or not val.strip()
            ):
                raise SessionHeaderError(
                    f"{field_name} must be None or nonempty string: {val!r}"
                )
        if not isinstance(self.software_revision, str) or not self.software_revision.strip():
            raise SessionHeaderError(
                f"software_revision must be a nonempty string: "
                f"{self.software_revision!r}"
            )


@dataclass
class EEGPacket:
    sequence: int
    timestamp_us: int
    sample_rate: float
    channel_count: int
    samples: List[List[float]]
    status: int = 0
    quality: float = 1.0

    @classmethod
    def from_dict(cls, data: dict) -> "EEGPacket":
        try:
            return cls(
                sequence=int(data["sequence"]),
                timestamp_us=int(data["timestamp_us"]),
                sample_rate=float(data["sample_rate"]),
                channel_count=int(data["channel_count"]),
                samples=data["samples"],
                status=int(data.get("status", 0)),
                quality=float(data.get("quality", 1.0)),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise PacketValidationError(f"malformed packet fields: {e}") from e

    def n_samples(self) -> int:
        return len(self.samples)

    def expected_duration_us(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return (self.n_samples() / self.sample_rate) * 1_000_000.0

    def validate(
        self,
        header: SessionHeader,
        *,
        last_seq: Optional[int] = None,
        last_ts: Optional[int] = None,
        session_id: str = "",
    ) -> None:
        sid = session_id or header.session_id
        prefix = f"session={sid!r} seq={self.sequence}"

        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise PacketValidationError(
                f"{prefix}: sequence must be a nonnegative integer, got {self.sequence!r}"
            )
        if not isinstance(self.timestamp_us, int) or self.timestamp_us < 0:
            raise PacketValidationError(
                f"{prefix}: timestamp_us must be a nonnegative integer, "
                f"got {self.timestamp_us!r}"
            )
        if self.channel_count != header.channel_count:
            raise PacketValidationError(
                f"{prefix}: channel_count {self.channel_count} != "
                f"header {header.channel_count}"
            )
        if not math.isfinite(self.sample_rate) or abs(
            self.sample_rate - header.sample_rate
        ) > 1e-9:
            raise PacketValidationError(
                f"{prefix}: sample_rate {self.sample_rate} != "
                f"header {header.sample_rate}"
            )
        if not self.samples:
            raise PacketValidationError(
                f"{prefix}: empty packet rejected (no samples)"
            )
        if not isinstance(self.samples, list):
            raise PacketValidationError(
                f"{prefix}: samples must be a list of rows"
            )
        for i, row in enumerate(self.samples):
            if not isinstance(row, (list, tuple)):
                raise PacketValidationError(
                    f"{prefix} sample_i={i}: row must be a list"
                )
            if len(row) != header.channel_count:
                raise PacketValidationError(
                    f"{prefix} sample_i={i}: width {len(row)} != "
                    f"channel_count {header.channel_count}"
                )
            for c, val in enumerate(row):
                try:
                    fval = float(val)
                except (TypeError, ValueError) as e:
                    raise PacketValidationError(
                        f"{prefix} sample_i={i} ch={c}: non-numeric value {val!r}"
                    ) from e
                if not math.isfinite(fval):
                    raise PacketValidationError(
                        f"{prefix} sample_i={i} ch={c}: non-finite value {val!r}"
                    )
        if not isinstance(self.status, int):
            raise PacketValidationError(
                f"{prefix}: status must be an integer, got {self.status!r}"
            )
        if not isinstance(self.quality, (int, float)) or not math.isfinite(
            self.quality
        ):
            raise PacketValidationError(
                f"{prefix}: quality must be finite, got {self.quality!r}"
            )
        if not (QUALITY_MIN <= float(self.quality) <= QUALITY_MAX):
            raise PacketValidationError(
                f"{prefix}: quality {self.quality} outside "
                f"[{QUALITY_MIN}, {QUALITY_MAX}]"
            )

        if last_seq is not None:
            expected = last_seq + 1
            if self.sequence < expected:
                if self.sequence == last_seq:
                    raise PacketValidationError(
                        f"{prefix}: duplicate sequence (last was {last_seq})"
                    )
                raise PacketValidationError(
                    f"{prefix}: sequence went backwards "
                    f"(expected {expected}, got {self.sequence})"
                )
            if self.sequence > expected:
                raise PacketValidationError(
                    f"{prefix}: sequence gap "
                    f"(expected {expected}, got {self.sequence})"
                )
        if last_ts is not None:
            if self.timestamp_us < last_ts:
                raise PacketValidationError(
                    f"{prefix}: timestamp went backwards "
                    f"({self.timestamp_us} < {last_ts})"
                )
            if self.timestamp_us == last_ts:
                raise PacketValidationError(
                    f"{prefix}: repeated timestamp {self.timestamp_us}"
                )


@dataclass
class ContinuityDiagnostics:
    packet_count: int = 0
    sample_count: int = 0
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    first_timestamp_us: Optional[int] = None
    last_timestamp_us: Optional[int] = None
    sequence_gaps: List[Dict[str, int]] = field(default_factory=list)
    duplicate_sequences: List[int] = field(default_factory=list)
    backward_timestamps: List[Dict[str, int]] = field(default_factory=list)
    repeated_timestamps: List[int] = field(default_factory=list)
    large_intervals: List[Dict[str, Any]] = field(default_factory=list)
    sample_rate_mismatches: int = 0
    channel_mismatches: int = 0
    empty_packets: int = 0
    non_finite_samples: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def ok(self) -> bool:
        return (
            not self.sequence_gaps
            and not self.duplicate_sequences
            and not self.backward_timestamps
            and not self.repeated_timestamps
            and not self.errors
            and self.sample_rate_mismatches == 0
            and self.channel_mismatches == 0
            and self.empty_packets == 0
            and self.non_finite_samples == 0
        )


@dataclass
class SessionFinalization:
    record_type: str = "finalization"
    session_id: str = ""
    format: str = FORMAT
    version: int = VERSION_V2
    packet_count: int = 0
    sample_count: int = 0
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    first_timestamp_us: Optional[int] = None
    last_timestamp_us: Optional[int] = None
    sha256: str = ""
    status: str = "finalized"

    @classmethod
    def from_dict(cls, data: dict) -> "SessionFinalization":
        if data.get("record_type") != "finalization":
            raise SessionIntegrityError(
                f"expected finalization record, got {data.get('record_type')!r}"
            )
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    def to_dict(self) -> dict:
        return asdict(self)


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_content_digest(path: Path, *, exclude_final_line: bool = True) -> str:
    raw = path.read_bytes()
    if not exclude_final_line:
        return _sha256_of_bytes(raw)

    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    if not lines:
        return _sha256_of_bytes(b"")

    last_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            last_idx = i
            break
    if last_idx is None:
        return _sha256_of_bytes(b"")

    try:
        obj = json.loads(lines[last_idx])
        if isinstance(obj, dict) and obj.get("record_type") == "finalization":
            body = "".join(lines[:last_idx]).encode("utf-8")
            return _sha256_of_bytes(body)
    except (json.JSONDecodeError, TypeError):
        pass
    return _sha256_of_bytes(raw)
