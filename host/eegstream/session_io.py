"""Session writer/reader: atomic publication and streaming validation."""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Iterator, List, Optional, TextIO, Union

from host.eegstream.session_core import (
    FORMAT,
    VERSION_V1,
    VERSION_V2,
    SUPPORTED_VERSIONS,
    SessionError,
    SessionHeaderError,
    PacketValidationError,
    SessionIncompleteError,
    SessionIntegrityError,
    SessionHeader,
    EEGPacket,
    ContinuityDiagnostics,
    SessionFinalization,
    compute_content_digest,
)


class SessionWriter:
    """Atomically publish finalized sessions. Never overwrites by default.

    Writes go to a temporary file in the destination directory. The final
    path is published only after successful finalization via rename.
    Incomplete temps are removed on failure or context-manager exit without
    finalize().
    """

    def __init__(
        self,
        path: Union[str, Path],
        header: SessionHeader,
        *,
        overwrite: bool = False,
        version: int = VERSION_V2,
    ):
        header.validate()
        self.path = Path(path)
        if self.path.exists() and not overwrite:
            raise FileExistsError(
                f"refusing to overwrite existing session: {self.path}. "
                f"Pass overwrite=True only for controlled fixtures."
            )
        self.header = header
        if version not in SUPPORTED_VERSIONS:
            raise SessionHeaderError(f"unsupported write version: {version}")
        self._write_version = version
        self.header.version = version

        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        self._tmp_path = Path(tmp_name)
        self._fh: TextIO = os.fdopen(fd, "w", encoding="utf-8")
        self._published = False
        self._closed = False
        self._last_seq: Optional[int] = None
        self._last_ts: Optional[int] = None
        self._packet_count = 0
        self._sample_count = 0
        self._first_seq: Optional[int] = None
        self._first_ts: Optional[int] = None

        header_line = json.dumps(asdict(self.header), separators=(",", ":")) + "\n"
        self._fh.write(header_line)

    def write_packet(self, packet: EEGPacket) -> None:
        if self._closed:
            raise SessionError("write_packet on closed SessionWriter")
        packet.validate(
            self.header,
            last_seq=self._last_seq,
            last_ts=self._last_ts,
            session_id=self.header.session_id,
        )
        line = json.dumps(asdict(packet), separators=(",", ":")) + "\n"
        self._fh.write(line)
        if self._first_seq is None:
            self._first_seq = packet.sequence
            self._first_ts = packet.timestamp_us
        self._last_seq = packet.sequence
        self._last_ts = packet.timestamp_us
        self._packet_count += 1
        self._sample_count += packet.n_samples()

    def finalize(self) -> SessionFinalization:
        """Flush, compute digest, write finalization record, publish atomically."""
        if self._closed and self._published:
            raise SessionError("session already finalized")
        if self._closed:
            raise SessionError("cannot finalize a closed incomplete writer")

        self._fh.flush()
        os.fsync(self._fh.fileno())

        digest = compute_content_digest(self._tmp_path, exclude_final_line=False)

        fin = SessionFinalization(
            session_id=self.header.session_id,
            format=FORMAT,
            version=self._write_version,
            packet_count=self._packet_count,
            sample_count=self._sample_count,
            first_sequence=self._first_seq,
            last_sequence=self._last_seq,
            first_timestamp_us=self._first_ts,
            last_timestamp_us=self._last_ts,
            sha256=digest,
            status="finalized",
        )

        if self._write_version >= VERSION_V2:
            fin_line = json.dumps(fin.to_dict(), separators=(",", ":")) + "\n"
            self._fh.write(fin_line)
            self._fh.flush()
            os.fsync(self._fh.fileno())

        self._fh.close()
        self._closed = True

        os.replace(str(self._tmp_path), str(self.path))
        self._published = True
        return fin

    def abort(self) -> None:
        """Discard incomplete temporary recording."""
        if self._published:
            return
        if not self._closed:
            try:
                self._fh.close()
            except Exception:
                pass
            self._closed = True
        if self._tmp_path.exists():
            try:
                self._tmp_path.unlink()
            except OSError:
                pass

    def close(self) -> None:
        """Close without publishing if not finalized (cleanup temp)."""
        if self._published:
            return
        self.abort()

    def __enter__(self) -> "SessionWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.abort()
            return
        if not self._published and not self._closed:
            try:
                self.finalize()
            except Exception:
                self.abort()
                raise


class SessionReader:
    """Streaming reader with incremental validation and integrity checks.

    Prefer iterating packets() over channels() for large sessions.
    """

    def __init__(
        self,
        path: Union[str, Path],
        *,
        strict: bool = True,
        require_finalization: bool = False,
        verify_digest: bool = True,
    ):
        self.path = Path(path)
        self.strict = strict
        self.require_finalization = require_finalization
        self.verify_digest = verify_digest
        self.header: SessionHeader
        self.finalization: Optional[SessionFinalization] = None
        self._header_line_no = 1
        self._load_header_and_scan()

    def _load_header_and_scan(self) -> None:
        if not self.path.is_file():
            raise SessionError(f"session file not found: {self.path}")

        packet_line_nos: List[int] = []
        finalization_data: Optional[dict] = None
        header_obj: Optional[dict] = None
        line_no = 0
        truncated = False

        with self.path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line_no += 1
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError as e:
                    msg = (
                        f"malformed JSON at line {line_no} in {self.path}: {e}"
                    )
                    if self.strict:
                        raise SessionError(msg) from e
                    truncated = True
                    continue
                if not isinstance(obj, dict):
                    raise SessionError(
                        f"line {line_no}: expected JSON object, got {type(obj).__name__}"
                    )
                if header_obj is None:
                    header_obj = obj
                    self._header_line_no = line_no
                    continue
                if obj.get("record_type") == "finalization":
                    finalization_data = obj
                    continue
                packet_line_nos.append(line_no)

        if header_obj is None:
            raise SessionError(f"empty or headerless session: {self.path}")

        self.header = SessionHeader.from_dict(header_obj)
        self.header.validate()

        if finalization_data is not None:
            self.finalization = SessionFinalization.from_dict(finalization_data)
            if self.verify_digest:
                expected = self.finalization.sha256
                actual = compute_content_digest(self.path, exclude_final_line=True)
                if actual != expected:
                    raise SessionIntegrityError(
                        f"session={self.header.session_id!r}: digest mismatch "
                        f"(expected {expected}, got {actual})"
                    )
        else:
            self.finalization = None
            if self.require_finalization or (
                self.strict and self.header.version >= VERSION_V2
            ):
                raise SessionIncompleteError(
                    f"session={self.header.session_id!r}: missing finalization record "
                    f"(version={self.header.version})"
                )

        self._packet_line_nos = packet_line_nos
        self._truncated_flag = truncated

    def is_finalized(self) -> bool:
        return self.finalization is not None and self.finalization.status == "finalized"

    def packets(self) -> Iterator[EEGPacket]:
        last_seq: Optional[int] = None
        last_ts: Optional[int] = None
        line_no = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line_no += 1
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError as e:
                    raise SessionError(
                        f"malformed JSON at line {line_no} in {self.path}: {e}"
                    ) from e
                if line_no == self._header_line_no:
                    continue
                if isinstance(obj, dict) and obj.get("record_type") == "finalization":
                    continue
                packet = EEGPacket.from_dict(obj)
                packet.validate(
                    self.header,
                    last_seq=last_seq,
                    last_ts=last_ts,
                    session_id=self.header.session_id,
                )
                last_seq = packet.sequence
                last_ts = packet.timestamp_us
                yield packet

    def diagnose(self) -> ContinuityDiagnostics:
        """Collect structured continuity diagnostics without raising on gaps."""
        diag = ContinuityDiagnostics()
        last_seq: Optional[int] = None
        last_ts: Optional[int] = None
        line_no = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line_no += 1
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError as e:
                    diag.errors.append(f"line {line_no}: malformed JSON: {e}")
                    continue
                if line_no == self._header_line_no:
                    continue
                if isinstance(obj, dict) and obj.get("record_type") == "finalization":
                    continue
                try:
                    packet = EEGPacket.from_dict(obj)
                except PacketValidationError as e:
                    diag.errors.append(str(e))
                    continue

                diag.packet_count += 1
                diag.sample_count += packet.n_samples()
                if diag.first_sequence is None:
                    diag.first_sequence = packet.sequence
                    diag.first_timestamp_us = packet.timestamp_us
                diag.last_sequence = packet.sequence
                diag.last_timestamp_us = packet.timestamp_us

                if packet.channel_count != self.header.channel_count:
                    diag.channel_mismatches += 1
                if abs(packet.sample_rate - self.header.sample_rate) > 1e-9:
                    diag.sample_rate_mismatches += 1
                if not packet.samples:
                    diag.empty_packets += 1
                for row in packet.samples:
                    for val in row:
                        try:
                            if not math.isfinite(float(val)):
                                diag.non_finite_samples += 1
                        except (TypeError, ValueError):
                            diag.non_finite_samples += 1

                if last_seq is not None:
                    expected = last_seq + 1
                    if packet.sequence == last_seq:
                        diag.duplicate_sequences.append(packet.sequence)
                    elif packet.sequence != expected:
                        diag.sequence_gaps.append(
                            {
                                "expected": expected,
                                "got": packet.sequence,
                                "gap": packet.sequence - expected,
                            }
                        )
                if last_ts is not None:
                    if packet.timestamp_us < last_ts:
                        diag.backward_timestamps.append(
                            {
                                "seq": packet.sequence,
                                "ts": packet.timestamp_us,
                                "prev": last_ts,
                            }
                        )
                    elif packet.timestamp_us == last_ts:
                        diag.repeated_timestamps.append(packet.timestamp_us)
                    else:
                        nominal = packet.expected_duration_us()
                        delta = packet.timestamp_us - last_ts
                        if nominal > 0 and delta > 10 * nominal:
                            diag.large_intervals.append(
                                {
                                    "seq": packet.sequence,
                                    "delta_us": delta,
                                    "nominal_us": nominal,
                                }
                            )
                last_seq = packet.sequence
                last_ts = packet.timestamp_us
        return diag

    def channels(self) -> List[List[float]]:
        chans: List[List[float]] = [[] for _ in range(self.header.channel_count)]
        for packet in self.packets():
            for row in packet.samples:
                for c, value in enumerate(row):
                    chans[c].append(float(value))
        return chans

    def sample_count(self) -> int:
        if self.finalization is not None:
            return self.finalization.sample_count
        return sum(p.n_samples() for p in self.packets())

    def packet_count(self) -> int:
        if self.finalization is not None:
            return self.finalization.packet_count
        return sum(1 for _ in self.packets())

    def duration_seconds(self) -> float:
        n = self.sample_count()
        if self.header.sample_rate <= 0:
            return 0.0
        return n / self.header.sample_rate

    def integrity_report(self) -> dict:
        """Machine-readable integrity summary."""
        dig_ok: Optional[bool] = None
        dig_actual: Optional[str] = None
        if self.finalization is not None:
            dig_actual = compute_content_digest(self.path, exclude_final_line=True)
            dig_ok = dig_actual == self.finalization.sha256
        return {
            "path": str(self.path),
            "session_id": self.header.session_id,
            "format": self.header.format,
            "version": self.header.version,
            "finalized": self.is_finalized(),
            "packet_count": self.packet_count(),
            "sample_count": self.sample_count(),
            "duration_s": self.duration_seconds(),
            "digest_ok": dig_ok,
            "digest_sha256": dig_actual
            if dig_actual is not None
            else (
                self.finalization.sha256 if self.finalization else None
            ),
            "finalization": self.finalization.to_dict()
            if self.finalization
            else None,
        }


def write_synthetic(
    path: Path,
    *,
    session_id: str = "synthetic",
    sample_rate: float = 250.0,
    channel_count: int = 2,
    n_samples: int = 250,
    packet_size: int = 25,
    created_at: str = "2026-08-31T00:00:00Z",
    overwrite: bool = True,
    version: int = VERSION_V2,
) -> SessionHeader:
    """Deterministic fixture writer. Not a physiological model.

    overwrite defaults to True for test fixtures so existing temp paths can be
    replaced safely. Production recording must use SessionWriter with
    overwrite=False (the default).
    """
    names = [f"ch{i+1}" for i in range(channel_count)]
    header = SessionHeader(
        session_id=session_id,
        sample_rate=sample_rate,
        channel_count=channel_count,
        channel_names=names,
        source="synthetic",
        created_at=created_at,
        version=version,
    )
    with SessionWriter(path, header, overwrite=overwrite, version=version) as writer:
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
