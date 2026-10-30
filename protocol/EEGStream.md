# EEGStream Protocol

Stable acquisition protocol for eeg-loop.

The protocol exists so raw acquisition can be replayed later through the same
processing, inference, and control pipelines without hardware attached.

```
recorded data
     |
same processing pipeline
     |
same inference pipeline
     |
same controller
```

## Architectural rule

**Raw EEG recordings are immutable evidence.**

Analysis, filtering, feature extraction, and inference must operate on derived
data without modifying the original session. Derived artifacts live next to the
session (experiment `derived/`), never inside the raw `.eeg` as a replacement.

## Conceptual packet

```
EEGPacket
  sequence
  timestamp_us
  sample_rate
  channel_count
  samples[]
  status
  quality
```

Each sample must be traceable to:

- sequence number
- timestamp
- channel
- sample value

`sample_rate` is carried in the packet / session header. It is selected from the
AFE configuration and intended bandwidth. Do not treat 250 Hz as a hard requirement.

## Wire intent (firmware to host)

Firmware job only:

```
initialize ADS1299
        |
configure sampling
        |
read samples
        |
timestamp
        |
packetize
        |
USB serial
```

Firmware does not perform inference.

Until the USB framing is frozen on hardware, host tools persist the same fields
in the session format below. Changing wire bytes later must not change field meaning.

### Field semantics

| Field | Meaning |
| --- | --- |
| `sequence` | Monotonic packet counter starting at 0. Gaps are dropped packets. Duplicates are protocol errors. |
| `timestamp_us` | Firmware time of the **first sample** in the packet, microseconds since boot. Must be nondecreasing; equal timestamps are rejected. |
| `sample_rate` | Nominal samples per second per channel (must match session header). |
| `channel_count` | Number of stored channels (must match session header). |
| `samples` | List of rows; `samples[i][c]` is sample `i` of channel `c` inside this packet. Raw converter values (not filtered). Empty packets are rejected. |
| `status` | Integer bitfield: streaming, overflow, lead-off, clock-error, etc. |
| `quality` | Coarse on-device quality hint in `[0, 1]`. Host quality metrics override this. |

### Packet duration

Nominal packet duration is:

```
duration_us = (n_samples / sample_rate) * 1_000_000
```

Do not assume every packet timestamp represents an individual sample timestamp.
Large intervals (> 10× nominal packet duration) are reported as diagnostics;
they are not auto-repaired.

### Host validation (recorder and reader)

The recorder and reader must guarantee:

- no silent overwrite of an existing finalized session
- atomic publication (temp → rename after successful finalization)
- incomplete temps cleaned up on failure
- sequence continuity (gaps and duplicates raise)
- timestamp monotonicity (backward and repeated raise)
- channel and sample-rate match header
- every sample value is finite
- quality in `[0, 1]`
- empty packets rejected
- corrupt or incomplete sessions explicitly identified

Preserve raw data. Do not aggressively filter the only copy. Do not invent
replacement samples or timestamps.

## Session file (`.eeg`)

Host-side immutable session. JSON Lines (UTF-8).

### Version 1 (legacy, still readable)

Line 1 is the header; subsequent lines are packets. No finalization record.

### Version 2 (current write default)

Line 1 is the header. Following lines are packets. The **last** non-empty line
is a finalization record.

Header:

```json
{
  "format": "eeg-loop.session",
  "version": 2,
  "session_id": "session-001",
  "sample_rate": 250.0,
  "channel_count": 2,
  "channel_names": ["ch1", "ch2"],
  "units": "raw_counts",
  "source": "synthetic|usb",
  "created_at": "2026-08-31T00:00:00Z",
  "hardware_revision": null,
  "firmware_revision": null,
  "software_revision": "0.1.0-scaffold"
}
```

Packet:

```json
{
  "sequence": 0,
  "timestamp_us": 0,
  "sample_rate": 250.0,
  "channel_count": 2,
  "samples": [[12.0, -3.0], [11.0, -2.5]],
  "status": 0,
  "quality": 1.0
}
```

Finalization (v2 only):

```json
{
  "record_type": "finalization",
  "session_id": "session-001",
  "format": "eeg-loop.session",
  "version": 2,
  "packet_count": 10,
  "sample_count": 250,
  "first_sequence": 0,
  "last_sequence": 9,
  "first_timestamp_us": 0,
  "last_timestamp_us": 900000,
  "sha256": "<hex>",
  "status": "finalized"
}
```

### Digest

SHA-256 over every byte of the file **before** the finalization line (header +
all packet lines, including their trailing newlines). The finalization record
is excluded to avoid circular hashing. Independent verification recomputes the
digest from the on-disk content and compares it to `sha256`.

A session missing its finalization record is not reported as fully finalized.
Strict readers of v2 sessions require the record; v1 sessions remain readable
without it.

### Session lifecycle

```
open writer (refuse if destination exists)
  → write header to temp file in destination directory
  → write packets (validated)
  → finalize: fsync, compute digest, write finalization, fsync
  → atomic rename temp → destination
```

On any failure before rename: delete temp; destination (if any) is untouched.

### Recovery from interrupted recording

An incomplete temporary file (`.name.*.tmp` in the destination directory) is
never a published session. Readers only open the final path. Interrupted runs
leave no partially published `.eeg`.

## Continuity diagnostics

Structured diagnostics distinguish:

- sequence gaps
- duplicate sequences
- backward timestamps
- repeated timestamps
- unexpectedly large timestamp intervals
- sample-rate / channel mismatches
- empty packets / non-finite samples

Diagnostics do not repair data.

## CLI

```bash
python3 -m host.tools.eeg_record --synthetic --output session.eeg
python3 -m host.tools.eeg_inspect session.eeg
python3 -m host.tools.eeg_inspect session.eeg --json
python3 -m host.tools.eeg_inspect session.eeg --validate-only --require-finalization
python3 -m host.tools.eeg_replay session.eeg
python3 -m host.tools.eeg_export session.eeg --format csv
```

`eeg_inspect` exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Valid (and finalized if required) |
| 1 | Invalid / malformed session |
| 2 | Incomplete (missing finalization when required) |
| 3 | Integrity digest mismatch |

## Derived data

Derived features, filters, PSD, baselines, and controller traces live next to
the session (experiment `derived/`), never inside the raw `.eeg` as a replacement.
