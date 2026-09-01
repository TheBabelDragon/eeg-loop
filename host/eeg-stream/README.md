# host/eeg-stream

Immutable session I/O for EEGStream.

```
RAW
 |
immutable session
 |
derived processing
```

The recorder must guarantee:

- no dropped packets
- no silent timestamp discontinuities
- sequence validation
- channel validation
- sample-rate validation
- corruption detection

Preserve raw data. Do not aggressively filter the only copy.

Python package lives at `host/eegstream/` so tools and tests share one reader/writer.
