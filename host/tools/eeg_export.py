from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from host.eegstream.session import SessionReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export derived views of a raw session. Does not modify the .eeg."
    )
    parser.add_argument("session", type=Path)
    parser.add_argument("--format", choices=["csv"], default="csv")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    session = SessionReader(args.session)
    channels = session.channels()
    names = session.header.channel_names or [
        f"ch{i+1}" for i in range(session.header.channel_count)
    ]
    out = args.output
    if out is None:
        out = args.session.with_suffix(".csv")

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["index", "t_s", *names])
        n = len(channels[0]) if channels else 0
        sr = session.header.sample_rate
        for i in range(n):
            row = [i, i / sr] + [channels[c][i] for c in range(len(channels))]
            writer.writerow(row)
    print(f"exported {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
