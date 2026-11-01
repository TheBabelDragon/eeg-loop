"""Deterministic ADS1299 simulator for host-side testing.

Implements the same conceptual acquisition interface as the firmware AFE
backend: configuration, sample production, sequence/timestamp progression,
and status bitfields (lead-off, overflow).

The simulator NEVER represents real EEG. All outputs are synthetic and
labeled as such in session headers (source=\"simulated\").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from host.eegstream.session_core import EEGPacket


# Status bitfield (matches firmware intent)
STATUS_STREAMING = 1 << 0
STATUS_OVERFLOW = 1 << 1
STATUS_LEAD_OFF = 1 << 2
STATUS_CLOCK_ERROR = 1 << 3
STATUS_CONFIG_ERROR = 1 << 4


@dataclass
class SimulatorConfig:
    sample_rate: float = 250.0
    channel_count: int = 2
    samples_per_packet: int = 25  # 100 ms @ 250 Hz
    seed: int = 42
    # Injected fault schedule: sequence -> status bits to OR in
    fault_at: dict = field(default_factory=dict)
    # Sequences that should be dropped (simulates lost packets)
    drop_sequences: Sequence[int] = field(default_factory=list)
    # Force disconnect after this many packets (None = never)
    disconnect_after: Optional[int] = None


class SimulatedADS1299:
    """Deterministic multi-channel sample generator with fault injection.

    Produces differential-like synthetic waveforms (sum of sinusoids +
    low-level noise from a simple LCG) so downstream filters see non-zero
    energy without claiming biological origin.
    """

    def __init__(self, config: Optional[SimulatorConfig] = None):
        self.config = config or SimulatorConfig()
        self._seq = 0
        self._timestamp_us = 0
        self._packets_emitted = 0
        self._rng = self.config.seed & 0xFFFFFFFF
        self._configured = False
        self._running = False
        self._overflow = False
        self._lead_off_mask = 0  # bit per channel

    def configure(
        self,
        sample_rate: float,
        channel_count: int,
        *,
        samples_per_packet: Optional[int] = None,
    ) -> None:
        if sample_rate <= 0 or not math.isfinite(sample_rate):
            raise ValueError(f"invalid sample_rate: {sample_rate}")
        if channel_count < 1:
            raise ValueError(f"invalid channel_count: {channel_count}")
        self.config.sample_rate = float(sample_rate)
        self.config.channel_count = int(channel_count)
        if samples_per_packet is not None:
            if samples_per_packet < 1:
                raise ValueError("samples_per_packet must be >= 1")
            self.config.samples_per_packet = int(samples_per_packet)
        self._configured = True
        self._running = False
        self._seq = 0
        self._timestamp_us = 0
        self._packets_emitted = 0

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("ADS1299 simulator not configured")
        self._running = True

    def stop(self) -> None:
        self._running = False

    def inject_lead_off(self, channel_mask: int) -> None:
        self._lead_off_mask = int(channel_mask) & 0xFF

    def inject_overflow(self, enabled: bool = True) -> None:
        self._overflow = bool(enabled)

    def _next_rng(self) -> float:
        # Simple LCG for deterministic "noise"
        self._rng = (1103515245 * self._rng + 12345) & 0x7FFFFFFF
        return (self._rng / 0x7FFFFFFF) * 2.0 - 1.0

    def _sample_value(self, channel: int, sample_index: int) -> float:
        """Synthetic differential-like signal in raw converter counts scale."""
        t = (self._timestamp_us / 1_000_000.0) + (
            sample_index / self.config.sample_rate
        )
        # Distinct tones per channel so cross-channel tests are meaningful
        f1 = 10.0 + channel * 3.0  # alpha-ish
        f2 = 40.0 + channel * 5.0  # gamma-ish
        base = 200.0 * math.sin(2 * math.pi * f1 * t)
        base += 50.0 * math.sin(2 * math.pi * f2 * t)
        base += 5.0 * self._next_rng()
        return base

    def next_packet(self) -> Optional[EEGPacket]:
        """Produce the next acquisition packet, or None if disconnected/stopped."""
        if not self._running:
            return None
        if (
            self.config.disconnect_after is not None
            and self._packets_emitted >= self.config.disconnect_after
        ):
            self._running = False
            return None

        # Skip dropped sequences
        while self._seq in self.config.drop_sequences:
            self._seq += 1
            # Advance time as if the packet existed
            n = self.config.samples_per_packet
            self._timestamp_us += int(
                round((n / self.config.sample_rate) * 1_000_000.0)
            )

        n = self.config.samples_per_packet
        ch = self.config.channel_count
        samples: List[List[float]] = []
        for i in range(n):
            row = [self._sample_value(c, i) for c in range(ch)]
            samples.append(row)

        status = STATUS_STREAMING
        if self._overflow:
            status |= STATUS_OVERFLOW
        if self._lead_off_mask:
            status |= STATUS_LEAD_OFF
        if self._seq in self.config.fault_at:
            status |= int(self.config.fault_at[self._seq])

        quality = 1.0
        if status & STATUS_LEAD_OFF:
            quality = 0.3
        if status & STATUS_OVERFLOW:
            quality = min(quality, 0.5)

        packet = EEGPacket(
            sequence=self._seq,
            timestamp_us=self._timestamp_us,
            sample_rate=self.config.sample_rate,
            channel_count=ch,
            samples=samples,
            status=status,
            quality=quality,
        )

        self._seq += 1
        self._timestamp_us += int(
            round((n / self.config.sample_rate) * 1_000_000.0)
        )
        self._packets_emitted += 1
        return packet

    @property
    def packets_emitted(self) -> int:
        return self._packets_emitted

    @property
    def is_running(self) -> bool:
        return self._running
