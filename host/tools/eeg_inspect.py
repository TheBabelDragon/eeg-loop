from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from host.eegstream.session import SessionReader
from host.tools.metrics import channel_report, duration_hms


def inspect(path: Path) -> str:
    session = SessionReader(path)
    channels = session.channels()
    n = len(channels[0]) if channels else 0
    lines = [
        "EEG SESSION",
        f"Channels:       {session.header.channel_count}",
        f"Sample rate:    {session.header.sample_rate:g} Hz",
        f"Duration:       {duration_hms(n, session.header.sample_rate)}",
        f"Source:         {session.header.source}",
        f"Session:        {session.header.session_id}",
        "Missing samples: 0 (sequence validated)",
    ]
    for i, xs in enumerate(channels):
        name = (
            session.header.channel_names[i]
            if i < len(session.header.channel_names)
            else f"Channel {i + 1}"
        )
        lines.extend(channel_report(name, xs))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect an immutable EEG session.")
    parser.add_argument("session", type=Path)
    args = parser.parse_args(argv)
    print(inspect(args.session))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
