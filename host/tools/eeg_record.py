from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from host.eegstream.session import write_synthetic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record an EEGStream session. Live USB is not wired in v0.1 scaffold."
    )
    parser.add_argument("--device", default="/dev/ttyACM0")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="write a deterministic fixture instead of opening serial",
    )
    parser.add_argument("--sample-rate", type=float, default=250.0)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--samples", type=int, default=250)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow replacing an existing session (default: refuse)",
    )
    args = parser.parse_args(argv)

    if not args.synthetic:
        print(
            "eeg-record: live USB path is not implemented.\n"
            f"  intended device: {args.device}\n"
            "  pass --synthetic to write a deterministic session for pipeline tests.",
            file=sys.stderr,
        )
        return 2

    if args.output.exists() and not args.overwrite:
        print(
            f"eeg-record: refusing to overwrite existing session {args.output}\n"
            "  pass --overwrite only for controlled fixtures.",
            file=sys.stderr,
        )
        return 1

    write_synthetic(
        args.output,
        session_id=args.output.stem,
        sample_rate=args.sample_rate,
        channel_count=args.channels,
        n_samples=args.samples,
        overwrite=args.overwrite or not args.output.exists(),
    )
    print(f"wrote synthetic session {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
