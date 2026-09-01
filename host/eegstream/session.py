from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, TextIO

FORMAT = "eeg-loop.session"
VERSION = 1


@dataclass
class SessionHeader:
    format: str = FORMAT
    version: int = VERSION
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
            raise ValueError(f"unknown session format: {self.format}")
        if self.version != VERSION:
            raise ValueError(f"unsupported session version: {self.version}")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be > 0")
        if self.channel_count < 1:
            raise ValueError("channel_count must be >= 1")


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
        return cls(
            sequence=int(data["sequence"]),
            timestamp_us=int(data["timestamp_us"]),
            sample_rate=float(data["sample_rate"]),
            channel_count=int(data["channel_count"]),
            samples=data["samples"],
            status=int(data.get("status", 0)),
            quality=float(data.get("quality", 1.0)),
        )

    def n_samples(self) -> int:
        return len(self.samples)

    def validate(self, header: SessionHeader) -> None:
        if self.channel_count != header.channel_count:
            raise ValueError(
                f"channel mismatch seq={self.sequence}: "
                f"{self.channel_count} != {header.channel_count}"
            )
        if abs(self.sample_rate - header.sample_rate) > 1e-9:
            raise ValueError(
                f"sample_rate mismatch seq={self.sequence}: "
                f"{self.sample_rate} != {header.sample_rate}"
            )
        for i, row in enumerate(self.samples):
            if len(row) != header.channel_count:
                raise ValueError(
                    f"bad sample width seq={self.sequence} i={i}: {len(row)}"
                )


class SessionWriter:
    def __init__(self, path: Path, header: SessionHeader):
        header.validate()
        self.path = Path(path)
        self.header = header
        self._fh: TextIO = self.path.open("w", encoding="utf-8")
        self._fh.write(json.dumps(asdict(header), separators=(",", ":")) + "\n")
        self._last_seq: Optional[int] = None
        self._last_ts: Optional[int] = None

    def write_packet(self, packet: EEGPacket) -> None:
        packet.validate(self.header)
        if self._last_seq is not None and packet.sequence != self._last_seq + 1:
            raise ValueError(
                f"sequence gap: expected {self._last_seq + 1}, got {packet.sequence}"
            )
        if self._last_ts is not None and packet.timestamp_us < self._last_ts:
            raise ValueError(
                f"timestamp went backwards at seq={packet.sequence}"
            )
        self._fh.write(json.dumps(asdict(packet), separators=(",", ":")) + "\n")
        self._last_seq = packet.sequence
        self._last_ts = packet.timestamp_us

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "SessionWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class SessionReader:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.header, self._packet_lines = self._load()
        self.header.validate()

    def _load(self) -> tuple[SessionHeader, List[str]]:
        text = self.path.read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            raise ValueError(f"empty session: {self.path}")
        header = SessionHeader.from_dict(json.loads(lines[0]))
        return header, lines[1:]

    def packets(self) -> Iterator[EEGPacket]:
        last_seq: Optional[int] = None
        last_ts: Optional[int] = None
        for raw in self._packet_lines:
            packet = EEGPacket.from_dict(json.loads(raw))
            packet.validate(self.header)
            if last_seq is not None and packet.sequence != last_seq + 1:
                raise ValueError(
                    f"sequence gap: expected {last_seq + 1}, got {packet.sequence}"
                )
            if last_ts is not None and packet.timestamp_us < last_ts:
                raise ValueError(
                    f"timestamp went backwards at seq={packet.sequence}"
                )
            last_seq = packet.sequence
            last_ts = packet.timestamp_us
            yield packet

    def channels(self) -> List[List[float]]:
        chans: List[List[float]] = [[] for _ in range(self.header.channel_count)]
        for packet in self.packets():
            for row in packet.samples:
                for c, value in enumerate(row):
                    chans[c].append(float(value))
        return chans

    def sample_count(self) -> int:
        return sum(p.n_samples() for p in self.packets())


def write_synthetic(
    path: Path,
    *,
    session_id: str = "synthetic",
    sample_rate: float = 250.0,
    channel_count: int = 2,
    n_samples: int = 250,
    packet_size: int = 25,
    created_at: str = "2026-08-31T00:00:00Z",
) -> SessionHeader:
    """Deterministic fixture writer. Not a physiological model."""
    names = [f"ch{i+1}" for i in range(channel_count)]
    header = SessionHeader(
        session_id=session_id,
        sample_rate=sample_rate,
        channel_count=channel_count,
        channel_names=names,
        source="synthetic",
        created_at=created_at,
    )
    with SessionWriter(path, header) as writer:
        seq = 0
        written = 0
        t = 0
        dt = int(round(1_000_000 * packet_size / sample_rate))
        while written < n_samples:
            take = min(packet_size, n_samples - written)
            samples: List[List[float]] = []
            for i in range(take):
                idx = written + i
                row = []
                for c in range(channel_count):
                    row.append(
                        (c + 1) * 10.0
                        + 3.0 * math.sin(2 * math.pi * 10 * idx / sample_rate)
                    )
                samples.append(row)
            writer.write_packet(
                EEGPacket(
                    sequence=seq,
                    timestamp_us=t,
                    sample_rate=sample_rate,
                    channel_count=channel_count,
                    samples=samples,
                )
            )
            written += take
            seq += 1
            t += dt
    return header
