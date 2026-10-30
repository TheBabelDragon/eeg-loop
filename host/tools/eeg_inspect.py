from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from host.eegstream.session import (
    SessionError,
    SessionIncompleteError,
    SessionIntegrityError,
    SessionReader,
)
from host.tools.metrics import channel_report, duration_hms


def inspect_text(path: Path, *, strict: bool = True) -> str:
    session = SessionReader(
        path,
        strict=strict,
        require_finalization=False,
        verify_digest=True,
    )
    n = session.sample_count()
    lines = [
        "EEG SESSION",
        f"Channels:       {session.header.channel_count}",
        f"Sample rate:    {session.header.sample_rate:g} Hz",
        f"Duration:       {duration_hms(n, session.header.sample_rate)}",
        f"Packets:        {session.packet_count()}",
        f"Samples:        {n}",
        f"Source:         {session.header.source}",
        f"Session:        {session.header.session_id}",
        f"Format/version: {session.header.format} v{session.header.version}",
        f"Finalized:      {session.is_finalized()}",
    ]
    if session.finalization is not None:
        lines.append(f"Digest SHA-256: {session.finalization.sha256}")
        lines.append(
            f"Seq range:      {session.finalization.first_sequence} .. "
            f"{session.finalization.last_sequence}"
        )
        lines.append(
            f"TS range (us):  {session.finalization.first_timestamp_us} .. "
            f"{session.finalization.last_timestamp_us}"
        )
    diag = session.diagnose()
    if diag.ok:
        lines.append("Continuity:     OK")
    else:
        lines.append("Continuity:     ISSUES")
        if diag.sequence_gaps:
            lines.append(f"  sequence gaps: {diag.sequence_gaps}")
        if diag.duplicate_sequences:
            lines.append(f"  duplicates:    {diag.duplicate_sequences}")
        if diag.backward_timestamps:
            lines.append(f"  backward ts:   {diag.backward_timestamps}")
        if diag.repeated_timestamps:
            lines.append(f"  repeated ts:   {diag.repeated_timestamps}")
        if diag.large_intervals:
            lines.append(f"  large gaps:    {len(diag.large_intervals)}")
        if diag.errors:
            lines.append(f"  errors:        {diag.errors}")
    channels = session.channels()
    for i, xs in enumerate(channels):
        name = (
            session.header.channel_names[i]
            if i < len(session.header.channel_names)
            else f"Channel {i + 1}"
        )
        lines.extend(channel_report(name, xs))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and validate an immutable EEG session."
    )
    parser.add_argument("session", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="machine-readable integrity + continuity report",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="exit after validation; no channel metrics",
    )
    parser.add_argument(
        "--require-finalization",
        action="store_true",
        help="fail if finalization record is absent",
    )
    parser.add_argument(
        "--no-verify-digest",
        action="store_true",
        help="skip SHA-256 verification",
    )
    args = parser.parse_args(argv)

    try:
        session = SessionReader(
            args.session,
            strict=True,
            require_finalization=args.require_finalization,
            verify_digest=not args.no_verify_digest,
        )
    except SessionIntegrityError as e:
        print(f"INTEGRITY FAILURE: {e}", file=sys.stderr)
        return 3
    except SessionIncompleteError as e:
        print(f"INCOMPLETE SESSION: {e}", file=sys.stderr)
        return 2
    except SessionError as e:
        print(f"INVALID SESSION: {e}", file=sys.stderr)
        return 1

    if args.json:
        report = session.integrity_report()
        report["continuity"] = session.diagnose().to_dict()
        print(json.dumps(report, indent=2))
        return 0

    if args.validate_only:
        print(
            f"OK session={session.header.session_id} "
            f"packets={session.packet_count()} samples={session.sample_count()} "
            f"finalized={session.is_finalized()}"
        )
        return 0

    print(inspect_text(args.session))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
