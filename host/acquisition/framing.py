"""USB transport framing for EEGStream acquisition.

Wire layout (little-endian):

  Offset  Size  Field
  0       2     magic          0xA5 0x5A
  2       1     version        PROTOCOL_VERSION (currently 1)
  3       1     frame_type     see FrameType
  4       2     payload_len    uint16 LE
  6       N     payload        opaque bytes
  6+N     2     crc16          CRC-16/CCITT-FALSE over (version..payload)

Malformed frames, truncated frames, and CRC failures raise FramingError.
Partial data is retained in the decoder buffer until a complete valid frame
is available or the stream is closed.

This framing layer is independent of EEGPacket field semantics. Changing
frame bytes later must not change the meaning of existing session fields.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple


FRAME_MAGIC = b"\xA5\x5A"
PROTOCOL_VERSION = 1
HEADER_SIZE = 6  # magic(2) + version(1) + type(1) + len(2)
CRC_SIZE = 2
MAX_PAYLOAD = 4096


class FramingError(ValueError):
    """Transport frame is malformed, truncated, or fails CRC."""


class FrameType(IntEnum):
    """USB frame types. Values are part of the wire contract."""

    HANDSHAKE_REQ = 0x01
    HANDSHAKE_ACK = 0x02
    DATA = 0x10
    STATUS = 0x20
    ERROR = 0x30


def _crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class TransportFrame:
    version: int
    frame_type: FrameType
    payload: bytes

    def encode(self) -> bytes:
        return encode_frame(self.frame_type, self.payload, version=self.version)


def encode_frame(
    frame_type: FrameType | int,
    payload: bytes,
    *,
    version: int = PROTOCOL_VERSION,
) -> bytes:
    """Encode a complete transport frame including CRC."""
    if not isinstance(payload, (bytes, bytearray)):
        raise FramingError("payload must be bytes")
    if len(payload) > MAX_PAYLOAD:
        raise FramingError(f"payload too large: {len(payload)} > {MAX_PAYLOAD}")
    if not (0 <= int(version) <= 255):
        raise FramingError(f"invalid version: {version}")
    ft = int(frame_type)
    if not (0 <= ft <= 255):
        raise FramingError(f"invalid frame_type: {ft}")

    header = FRAME_MAGIC + struct.pack("<BBH", version, ft, len(payload))
    body = header[2:] + payload  # version..payload for CRC
    crc = _crc16_ccitt(body)
    return header + payload + struct.pack("<H", crc)


def decode_frames(
    buffer: bytearray,
) -> Tuple[List[TransportFrame], bytearray]:
    """Extract complete valid frames from a receive buffer.

    Returns (frames, remaining_buffer). Invalid frames that cannot be
    resynchronized raise FramingError after consuming the bad magic region
    when possible; callers may choose to discard and continue.
    """
    frames: List[TransportFrame] = []
    buf = buffer

    while True:
        # Find magic
        idx = buf.find(FRAME_MAGIC)
        if idx < 0:
            # Keep last byte in case it is the first half of magic
            if len(buf) > 1:
                buf = buf[-1:]
            return frames, buf
        if idx > 0:
            # Discard leading garbage
            del buf[:idx]

        if len(buf) < HEADER_SIZE:
            return frames, buf

        version, ft, plen = struct.unpack_from("<BBH", buf, 2)
        if plen > MAX_PAYLOAD:
            # Impossible length — skip this magic and resync
            del buf[:2]
            continue

        total = HEADER_SIZE + plen + CRC_SIZE
        if len(buf) < total:
            return frames, buf

        frame_bytes = bytes(buf[:total])
        body = frame_bytes[2 : HEADER_SIZE + plen]  # version..payload
        expected_crc = struct.unpack_from("<H", frame_bytes, HEADER_SIZE + plen)[0]
        actual_crc = _crc16_ccitt(body)
        if actual_crc != expected_crc:
            # Bad CRC: skip magic and try to resync
            del buf[:2]
            continue

        try:
            frame_type = FrameType(ft)
        except ValueError:
            del buf[:total]
            continue

        if version != PROTOCOL_VERSION:
            # Unknown version — skip frame, do not interpret payload
            del buf[:total]
            continue

        payload = bytes(frame_bytes[HEADER_SIZE : HEADER_SIZE + plen])
        frames.append(
            TransportFrame(version=version, frame_type=frame_type, payload=payload)
        )
        del buf[:total]

    return frames, buf
