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

## Conceptual packet

```
EEGPacket
  sequence
  timestamp
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
| `sequence` | Monotonic packet counter. Gaps are dropped packets. |
| `timestamp` | Firmware time of the first sample in the packet, microseconds since boot. |
| `sample_rate` | Nominal samples per second per channel. |
| `channel_count` | Number of stored channels. |
| `samples` | Per-channel array of raw converter values (not filtered). |
| `status` | Bitfield: streaming, overflow, lead-off, clock-error, etc. |
| `quality` | Coarse on-device quality hint. Host quality metrics override this. |

### Host validation (recorder)

The recorder must guarantee:

- no dropped packets (or they are flagged, never silently filled)
- no silent timestamp discontinuities
- sequence validation
- channel validation
- sample-rate validation
- corruption detection

Preserve raw data. Do not aggressively filter the only copy.

## Session file (`.eeg`)

Host-side immutable session. JSON Lines.

Line 1 is the header:

```json
{
  "format": "eeg-loop.session",
  "version": 1,
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

Following lines are packets:

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

`samples[i][c]` is sample `i` of channel `c` inside this packet.

Replay walks packets in file order, checks sequence and timestamps, and feeds
the same sample stream the live recorder would have produced.

## Derived data

Derived features, filters, PSD, baselines, and controller traces live next to
the session (experiment `derived/`), never inside the raw `.eeg` as a replacement.
