"""Binary payload codec for EEGPacket over the transport frame.

DATA payload layout (little-endian), protocol_version == 1:

  Offset  Size   Field
  0       4      sequence          uint32
  4       8      timestamp_us      uint64
  12      4      sample_rate_x1000 uint32  (sample_rate * 1000, fixed-point)
  16      2      channel_count     uint16
  18      2      n_samples         uint16
  20      4      status            uint32 bitfield
  24      2      quality_x1000     uint16  (quality * 1000, [0,1000])
  26      N*C*4  samples           float32 LE, row-major [sample][channel]

Total header: 26 bytes + samples.

This binary layout is the wire representation only. Session storage remains
JSON Lines as defined in protocol/EEGStream.md. Field meanings are identical.
"""

from __future__ import annotations

import struct
from typing import List

from host.eegstream.session_core import EEGPacket


class PacketCodecError(ValueError):
    """Payload cannot be encoded or decoded as an EEGPacket."""


_HEADER_FMT = "<IQIHHIH"  # seq u32, ts u64, sr_x1000 u32, ch u16, n u16, status u32, q_x1000 u16
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 26


def encode_eeg_packet_payload(packet: EEGPacket) -> bytes:
    """Encode an EEGPacket into a DATA frame payload."""
    if packet.channel_count < 1:
        raise PacketCodecError("channel_count must be >= 1")
    if not packet.samples:
        raise PacketCodecError("empty packet rejected")
    n = len(packet.samples)
    for i, row in enumerate(packet.samples):
        if len(row) != packet.channel_count:
            raise PacketCodecError(
                f"sample {i} width {len(row)} != channel_count {packet.channel_count}"
            )

    sr_x1000 = int(round(float(packet.sample_rate) * 1000.0))
    q_x1000 = int(round(max(0.0, min(1.0, float(packet.quality))) * 1000.0))
    if not (0 <= packet.sequence < 2**32):
        raise PacketCodecError(f"sequence out of uint32 range: {packet.sequence}")
    if not (0 <= packet.timestamp_us < 2**64):
        raise PacketCodecError(f"timestamp_us out of uint64 range: {packet.timestamp_us}")

    header = struct.pack(
        _HEADER_FMT,
        int(packet.sequence),
        int(packet.timestamp_us),
        sr_x1000,
        int(packet.channel_count),
        n,
        int(packet.status) & 0xFFFFFFFF,
        q_x1000,
    )
    sample_bytes = b"".join(
        struct.pack(f"<{packet.channel_count}f", *[float(v) for v in row])
        for row in packet.samples
    )
    return header + sample_bytes


def decode_eeg_packet_payload(payload: bytes) -> EEGPacket:
    """Decode a DATA frame payload into an EEGPacket."""
    if len(payload) < _HEADER_SIZE:
        raise PacketCodecError(
            f"payload too short for header: {len(payload)} < {_HEADER_SIZE}"
        )
    (
        sequence,
        timestamp_us,
        sr_x1000,
        channel_count,
        n_samples,
        status,
        q_x1000,
    ) = struct.unpack_from(_HEADER_FMT, payload, 0)

    if channel_count < 1:
        raise PacketCodecError(f"invalid channel_count: {channel_count}")
    if n_samples < 1:
        raise PacketCodecError("empty packet rejected (n_samples=0)")

    expected = _HEADER_SIZE + n_samples * channel_count * 4
    if len(payload) != expected:
        raise PacketCodecError(
            f"payload length {len(payload)} != expected {expected} "
            f"(n_samples={n_samples}, channels={channel_count})"
        )

    samples: List[List[float]] = []
    offset = _HEADER_SIZE
    row_fmt = f"<{channel_count}f"
    row_size = channel_count * 4
    for _ in range(n_samples):
        row = list(struct.unpack_from(row_fmt, payload, offset))
        samples.append(row)
        offset += row_size

    sample_rate = sr_x1000 / 1000.0
    quality = q_x1000 / 1000.0
    return EEGPacket(
        sequence=int(sequence),
        timestamp_us=int(timestamp_us),
        sample_rate=float(sample_rate),
        channel_count=int(channel_count),
        samples=samples,
        status=int(status),
        quality=float(quality),
    )
