# host/tools

- `eeg-record` — synthetic / simulated / live USB → immutable `.eeg`
- `eeg-inspect` — session quality / basic stats / integrity
- `eeg-replay` — feed a session through the inference stack
- `eeg-export` — derived export (CSV); never overwrites the raw session

```bash
# Offline fixture
python3 -m host.tools.eeg_record --synthetic --output /tmp/s.eeg

# Simulated acquisition bridge (framed transport, not real EEG)
python3 -m host.tools.eeg_record --simulate --packets 10 --output /tmp/sim.eeg

# Live USB (pyserial required; firmware must be streaming)
python3 -m host.tools.eeg_record --device /dev/ttyACM0 --output /tmp/live.eeg

python3 -m host.tools.eeg_inspect /tmp/sim.eeg --validate-only --require-finalization
python3 -m host.tools.eeg_replay /tmp/sim.eeg
python3 -m host.tools.eeg_export /tmp/sim.eeg --format csv
```

Live path options: `--sample-rate`, `--channels`, `--duration`, `--baud`, `--overwrite`.
Failed or interrupted recordings never publish a finalized session.
