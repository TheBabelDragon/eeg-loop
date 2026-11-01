"""ESP32-S3 / ADS1299 acquisition path for eeg-loop.

Layers:
  framing   — USB transport frames (magic, version, length, payload, CRC)
  packet    — binary EEGPacket payload encode/decode
  serial    — host serial reader with handshake + streaming decode
  simulator — deterministic ADS1299 + serial transport (never real EEG)

Physical hardware path and simulated path share the same framing and
EEGPacket semantics. Simulation is never presented as real EEG.
"""

from host.acquisition.framing import (
    FRAME_MAGIC,
    PROTOCOL_VERSION,
    FrameType,
    TransportFrame,
    encode_frame,
    decode_frames,
    FramingError,
)
from host.acquisition.packet_codec import (
    encode_eeg_packet_payload,
    decode_eeg_packet_payload,
    PacketCodecError,
)
from host.acquisition.serial_source import (
    SerialAcquisitionSource,
    SimulatedSerialTransport,
    AcquisitionError,
    DeviceInfo,
)
from host.acquisition.simulator import (
    SimulatedADS1299,
    SimulatorConfig,
)

__all__ = [
    "FRAME_MAGIC",
    "PROTOCOL_VERSION",
    "FrameType",
    "TransportFrame",
    "encode_frame",
    "decode_frames",
    "FramingError",
    "encode_eeg_packet_payload",
    "decode_eeg_packet_payload",
    "PacketCodecError",
    "SerialAcquisitionSource",
    "SimulatedSerialTransport",
    "AcquisitionError",
    "DeviceInfo",
    "SimulatedADS1299",
    "SimulatorConfig",
]
