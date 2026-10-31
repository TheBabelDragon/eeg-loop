# Browser EEG Laboratory

Experimental visualization and signal-analysis environment for EEG-like signals.

**All generated signals are SIMULATED.** This is not a medical device. No real hardware I/O. No stimulation.

## Launch (offline)

```bash
cd web
python3 -m http.server 8765
# open http://localhost:8765/
```

No build step, no bundler, no backend.

## Architecture

```
SignalSource
  └── SyntheticEEGSource   (seeded, deterministic)
  └── EEGPacketSource      (protocol/EEGStream.md session JSONL adapter)

ChannelBuffer[]            (circular, fixed capacity)
SignalAnalyzer             (windowed Hann PSD, band powers, stats)
ArtifactDetector           (coarse flags only)
WaveformRenderer / SpectrumRenderer  (Canvas 2D, rAF)
SessionRecorder / Player   (JSONL, raw immutable + derived separate)
```

Signal generation and analysis run on their own timers. Rendering uses `requestAnimationFrame` and never drives the sample clock.

### Real-side integration boundary

`EEGPacketSource` decodes packets matching `protocol/EEGStream.md` (session JSONL v1/v2) and calls the same `onFrame(frame, timestampUs)` callback. Visualization and analysis layers stay unchanged.

- **Now:** load a `.eeg` / JSONL session from disk (host `eeg_record` output or browser export).
- **Not yet:** WebSerial / WebUSB / live USB stream — same class, different transport into `load()` / constructor.

Gaps, duplicates, and non-finite samples are **diagnosed, never auto-repaired**.

## Analysis notes

- Hann-windowed one-sided PSD; Δf = sampleRate / Nfft
- Relative band powers preferred; absolute powers depend on window length
- Artifact probability ≥ 0.7 → `NO_VALID_INFERENCE`

## Tests

```bash
cd web && python3 -m http.server 8765
# open http://localhost:8765/tests/test-runner.html
# or: node --input-type=module -e "import('./tests/test-core.js')"
```

## Limitations

- Synthetic only — not physiological data
- Artifact detector is coarse, not clinical
- No WebSerial / WebUSB / real hardware in this milestone
