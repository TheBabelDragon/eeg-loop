from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from host.eegstream.session import SessionReader
from inference.pipeline import analyze_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay a recorded session through the inference stack."
    )
    parser.add_argument("session", type=Path)
    parser.add_argument("--json", action="store_true", help="print StateVector JSON")
    args = parser.parse_args(argv)
    session = SessionReader(args.session)
    state = analyze_session(session)
    if args.json:
        print(json.dumps(state.as_dict(), indent=2))
    else:
        print(state.format_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
