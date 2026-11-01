"""Host serial acquisition source.

Reads framed USB serial from an ESP32-S3 acquisition bridge (or a simulated
transport) and yields validated EEGPacket objects for SessionWriter.

Handshake:
  Host → device: HANDSHAKE_REQ  payload = "EEGLOOP\0" + desired sample_rate_x1000 (u32) + channels (u16)
  Device → host: HANDSHAKE_ACK  payload = device_id string + sample_rate_x1000 + channels + fw_rev

On mismatch of sample_rate / channels the host aborts before recording.
Disconnects and corrupted frames raise AcquisitionError; they never produce
silently incomplete finalized sessions.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Iterator, List, Optional, Protocol, Union

from host.acquisition.framing import (
    PROTOCOL_VERSION,
    FrameType,
    TransportFrame,
    encode_frame,
    decode_frames,
    FramingError,
)
from host.acquisition.packet_codec import (
    decode_eeg_packet_payload,
    encode_eeg_packet_payload,
    PacketCodecError,
)
from host.acquisition.simulator import SimulatedADS1299, SimulatorConfig
from host.eegstream.session_core import EEGPacket


class AcquisitionError(RuntimeError):
    """Serial acquisition failed (disconnect, protocol, validation)."""


@dataclass
class DeviceInfo:
    device_id: str
    sample_rate: float
    channel_count: int
    firmware_revision: str
    protocol_version: int = PROTOCOL_VERSION


class _ByteSource(Protocol):
    def read(self, size: int = 256) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


class SimulatedSerialTransport:
    """In-process byte pipe driven by SimulatedADS1299.

    Implements the same handshake + DATA frames as firmware so host code
    paths are exercised without hardware.
    """

    def __init__(
        self,
        simulator: Optional[SimulatedADS1299] = None,
        *,
        device_id: str = "sim-ads1299-v0",
        firmware_revision: str = "sim-0.1.0",
    ):
        self.simulator = simulator or SimulatedADS1299()
        self.device_id = device_id
        self.firmware_revision = firmware_revision
        self._rx = bytearray()
        self._tx = bytearray()
        self._closed = False
        self._handshaken = False
        self._produce = False
        self._configured_rate = 250.0
        self._configured_ch = 2

    def write(self, data: bytes) -> int:
        if self._closed:
            raise AcquisitionError("simulated transport closed")
        self._rx.extend(data)
        self._process_host_bytes()
        return len(data)

    def read(self, size: int = 256) -> bytes:
        if self._closed:
            return b""
        if self._handshaken and self._produce and self.simulator.is_running:
            for _ in range(4):
                pkt = self.simulator.next_packet()
                if pkt is None:
                    break
                payload = encode_eeg_packet_payload(pkt)
                self._tx.extend(encode_frame(FrameType.DATA, payload))
        out = bytes(self._tx[:size])
        del self._tx[:size]
        return out

    def start_streaming(self) -> None:
        self._produce = True

    def close(self) -> None:
        self._closed = True
        self._produce = False
        self.simulator.stop()

    def _process_host_bytes(self) -> None:
        frames, self._rx = decode_frames(self._rx)
        for fr in frames:
            if fr.frame_type == FrameType.HANDSHAKE_REQ:
                self._handle_handshake(fr.payload)

    def _handle_handshake(self, payload: bytes) -> None:
        if not payload.startswith(b"EEGLOOP\x00"):
            err = encode_frame(FrameType.ERROR, b"bad-magic")
            self._tx.extend(err)
            return
        rest = payload[8:]
        if len(rest) < 6:
            self._tx.extend(encode_frame(FrameType.ERROR, b"short-hs"))
            return
        sr_x1000, channels = struct.unpack_from("<IH", rest, 0)
        sample_rate = sr_x1000 / 1000.0
        self.simulator.configure(sample_rate, channels)
        self.simulator.start()
        self._configured_rate = sample_rate
        self._configured_ch = channels
        self._handshaken = True
        ack = (
            self.device_id.encode("utf-8")
            + b"\x00"
            + self.firmware_revision.encode("utf-8")
            + b"\x00"
            + struct.pack("<IH", sr_x1000, channels)
        )
        self._tx.extend(encode_frame(FrameType.HANDSHAKE_ACK, ack))


class SerialAcquisitionSource:
    """Host-side acquisition from a real or simulated serial transport."""

    def __init__(
        self,
        port: Union[str, SimulatedSerialTransport],
        *,
        baudrate: int = 921600,
        sample_rate: float = 250.0,
        channel_count: int = 2,
        timeout: float = 2.0,
        handshake_timeout: float = 3.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.sample_rate = sample_rate
        self.channel_count = channel_count
        self.timeout = timeout
        self.handshake_timeout = handshake_timeout
        self._ser: Optional[_ByteSource] = None
        self._buffer = bytearray()
        self._device: Optional[DeviceInfo] = None
        self._closed = False

    def open(self) -> DeviceInfo:
        if isinstance(self.port, SimulatedSerialTransport):
            self._ser = self.port
        else:
            try:
                import serial  # type: ignore
            except ImportError as e:
                raise AcquisitionError(
                    "pyserial is required for live USB acquisition. "
                    "Install with: pip install pyserial  "
                    "Or use --synthetic / SimulatedSerialTransport for tests."
                ) from e
            self._ser = serial.Serial(
                port=str(self.port),
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
        self._device = self._handshake()
        return self._device

    def _handshake(self) -> DeviceInfo:
        assert self._ser is not None
        sr_x1000 = int(round(self.sample_rate * 1000.0))
        req = b"EEGLOOP\x00" + struct.pack("<IH", sr_x1000, self.channel_count)
        self._ser.write(encode_frame(FrameType.HANDSHAKE_REQ, req))
        deadline = time.monotonic() + self.handshake_timeout
        while time.monotonic() < deadline:
            chunk = self._ser.read(512)
            if chunk:
                self._buffer.extend(chunk)
            frames, self._buffer = decode_frames(self._buffer)
            for fr in frames:
                if fr.frame_type == FrameType.HANDSHAKE_ACK:
                    return self._parse_ack(fr.payload)
                if fr.frame_type == FrameType.ERROR:
                    raise AcquisitionError(
                        f"device rejected handshake: {fr.payload!r}"
                    )
            time.sleep(0.01)
        raise AcquisitionError("handshake timeout — no HANDSHAKE_ACK received")

    def _parse_ack(self, payload: bytes) -> DeviceInfo:
        parts = payload.split(b"\x00", 2)
        if len(parts) < 3:
            raise AcquisitionError(f"malformed HANDSHAKE_ACK: {payload!r}")
        device_id = parts[0].decode("utf-8", errors="replace")
        fw_rev = parts[1].decode("utf-8", errors="replace")
        rest = parts[2]
        if len(rest) < 6:
            raise AcquisitionError("HANDSHAKE_ACK missing rate/channel fields")
        sr_x1000, channels = struct.unpack_from("<IH", rest, 0)
        rate = sr_x1000 / 1000.0
        if abs(rate - self.sample_rate) > 1e-3:
            raise AcquisitionError(
                f"sample_rate mismatch: host={self.sample_rate} device={rate}"
            )
        if channels != self.channel_count:
            raise AcquisitionError(
                f"channel_count mismatch: host={self.channel_count} device={channels}"
            )
        return DeviceInfo(
            device_id=device_id,
            sample_rate=rate,
            channel_count=channels,
            firmware_revision=fw_rev,
        )

    def packets(self) -> Iterator[EEGPacket]:
        """Yield validated EEGPackets until disconnect or close."""
        if self._ser is None or self._device is None:
            raise AcquisitionError("call open() before packets()")
        if isinstance(self.port, SimulatedSerialTransport):
            self.port.start_streaming()
        while not self._closed:
            chunk = self._ser.read(1024)
            if not chunk:
                if isinstance(self.port, SimulatedSerialTransport):
                    if not self.port.simulator.is_running:
                        return
                continue
            self._buffer.extend(chunk)
            try:
                frames, self._buffer = decode_frames(self._buffer)
            except FramingError as e:
                raise AcquisitionError(f"framing error: {e}") from e
            for fr in frames:
                if fr.frame_type == FrameType.DATA:
                    try:
                        pkt = decode_eeg_packet_payload(fr.payload)
                    except PacketCodecError as e:
                        raise AcquisitionError(f"packet decode: {e}") from e
                    yield pkt
                elif fr.frame_type == FrameType.ERROR:
                    raise AcquisitionError(f"device error frame: {fr.payload!r}")
                elif fr.frame_type == FrameType.STATUS:
                    pass

    def close(self) -> None:
        self._closed = True
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def __enter__(self) -> "SerialAcquisitionSource":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()
