# host/tools

First tools:

- `eeg-record` — USB serial to immutable `.eeg` (stub until firmware streams)
- `eeg-inspect` — session quality / basic stats
- `eeg-replay` — feed a session through the inference stack
- `eeg-export` — derived export (CSV); never overwrites the raw session

```bash
python3 -m host.tools.eeg_inspect tests/fixtures/session-synthetic.eeg
python3 -m host.tools.eeg_replay tests/fixtures/session-synthetic.eeg
python3 -m host.tools.eeg_export tests/fixtures/session-synthetic.eeg --format csv
```
