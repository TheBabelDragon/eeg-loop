"""Record an EEGStream session from synthetic, simulated, or live USB source.

CLI:
  python3 -m host.tools.eeg_record --synthetic --output session.eeg
  python3 -m host.tools.eeg_record --simulate --output session.eeg
  python3 -m host.tools.eeg_record --device /dev/ttyACM0 --output session.eeg

Live USB requires pyserial. Simulated and synthetic paths do not.
Interrupted or failed recordings never publish a finalized .eeg.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from host.eegstream.session import (
    SessionHeader,
    SessionWriter,
    VERSION_V2,
    write_synthetic,
)
from host.acquisition.serial_source import (
    AcquisitionError,
    SerialAcquisitionSource,
    SimulatedSerialTransport,
)
from host.acquisition.simulator import SimulatedADS1299, SimulatorConfig


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_from_source(
    source: SerialAcquisitionSource,
    output: Path,
    *,
    session_id: str,
    duration_s: Optional[float] = None,
    max_packets: Optional[int] = None,
    overwrite: bool = False,
    source_label: str = "usb",
    hardware_revision: Optional[str] = None,
    firmware_revision: Optional[str] = None,
) -> int:
    device = source._device
    if device is None:
        raise AcquisitionError("source not opened")

    header = SessionHeader(
        version=VERSION_V2,
        session_id=session_id,
        sample_rate=device.sample_rate,
        channel_count=device.channel_count,
        channel_names=[f"ch{i+1}" for i in range(device.channel_count)],
        units="raw_counts",
        source=source_label,
        created_at=_iso_now(),
        hardware_revision=hardware_revision,
        firmware_revision=firmware_revision or device.firmware_revision,
        software_revision="0.2.0-acquisition-bridge",
    )

    writer = SessionWriter(output, header, overwrite=overwrite, version=VERSION_V2)
    packet_count = 0
    t0 = time.monotonic()
    try:
        for packet in source.packets():
            writer.write_packet(packet)
            packet_count += 1
            if max_packets is not None and packet_count >= max_packets:
                break
            if duration_s is not None and (time.monotonic() - t0) >= duration_s:
                break
        fin = writer.finalize()
        print(
            f"recorded {fin.packet_count} packets "
            f"({fin.sample_count} samples) → {output}"
        )
        print(f"  digest={fin.sha256[:16]}…  source={source_label}")
        return 0
    except Exception:
        writer.abort()
        raise
    finally:
        source.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record an EEGStream session (synthetic, simulated, or live USB)."
    )
    parser.add_argument("--device", default="/dev/ttyACM0", help="serial device path")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="write a deterministic offline fixture (no serial, no simulator)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="use in-process ADS1299 simulator over framed transport (not real EEG)",
    )
    parser.add_argument("--sample-rate", type=float, default=250.0)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--samples", type=int, default=250, help="for --synthetic: total samples")
    parser.add_argument("--duration", type=float, default=None, help="seconds (live/simulate)")
    parser.add_argument("--packets", type=int, default=None, help="stop after N packets")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--overwrite", action="store_true", help="allow replacing existing session")
    args = parser.parse_args(argv)

    if args.synthetic and args.simulate:
        print("eeg-record: pass only one of --synthetic or --simulate", file=sys.stderr)
        return 2

    if args.output.exists() and not args.overwrite:
        print(
            f"eeg-record: refusing to overwrite existing session {args.output}\n"
            "  pass --overwrite only for controlled fixtures.",
            file=sys.stderr,
        )
        return 1

    session_id = args.output.stem

    if args.synthetic:
        write_synthetic(
            args.output,
            session_id=session_id,
            sample_rate=args.sample_rate,
            channel_count=args.channels,
            n_samples=args.samples,
            overwrite=args.overwrite or not args.output.exists(),
        )
        print(f"wrote synthetic session {args.output}")
        return 0

    if args.simulate:
        cfg = SimulatorConfig(
            sample_rate=args.sample_rate,
            channel_count=args.channels,
            samples_per_packet=max(1, int(args.sample_rate // 10)),
        )
        max_packets = args.packets
        duration = args.duration
        if max_packets is None and duration is None:
            max_packets = 10
        sim = SimulatedADS1299(cfg)
        transport = SimulatedSerialTransport(sim)
        source = SerialAcquisitionSource(
            transport, sample_rate=args.sample_rate, channel_count=args.channels
        )
        try:
            source.open()
            return record_from_source(
                source, args.output, session_id=session_id,
                duration_s=duration, max_packets=max_packets,
                overwrite=args.overwrite, source_label="simulated",
                firmware_revision="sim-0.1.0",
            )
        except AcquisitionError as e:
            print(f"eeg-record: acquisition failed: {e}", file=sys.stderr)
            return 3

    source = SerialAcquisitionSource(
        args.device, baudrate=args.baud,
        sample_rate=args.sample_rate, channel_count=args.channels,
    )
    try:
        source.open()
        return record_from_source(
            source, args.output, session_id=session_id,
            duration_s=args.duration, max_packets=args.packets,
            overwrite=args.overwrite, source_label="usb",
        )
    except AcquisitionError as e:
        print(f"eeg-record: acquisition failed: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"eeg-record: unexpected error: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
