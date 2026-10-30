"""Immutable EEGStream session I/O with integrity guarantees.

Core rule: raw EEG recordings are immutable evidence. Analysis operates on
derived data only. This module re-exports the public API from session_core
and session_io.
"""

from __future__ import annotations

from host.eegstream.session_core import (
    FORMAT,
    VERSION_V1,
    VERSION_V2,
    SUPPORTED_VERSIONS,
    QUALITY_MIN,
    QUALITY_MAX,
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
from host.eegstream.session_io import SessionWriter, SessionReader, write_synthetic

__all__ = [
    "FORMAT",
    "VERSION_V1",
    "VERSION_V2",
    "SUPPORTED_VERSIONS",
    "QUALITY_MIN",
    "QUALITY_MAX",
    "SessionError",
    "SessionHeaderError",
    "PacketValidationError",
    "SessionIncompleteError",
    "SessionIntegrityError",
    "SessionHeader",
    "EEGPacket",
    "ContinuityDiagnostics",
    "SessionFinalization",
    "SessionWriter",
    "SessionReader",
    "compute_content_digest",
    "write_synthetic",
]
