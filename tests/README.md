# Tests

Categories (flat modules so `tests/` does not shadow `inference/` or stdlib `signal`):

```
test_protocol_session.py     packet parsing, sequence, timestamp
test_signal_features.py      feature extraction / artifact flags
test_inference_replay.py     deterministic replay, baseline, confidence
test_control_placeholder.py  closed-loop not armed in v0.1
```

Most important path:

```
recorded EEG
    |
replay
    |
expected features
    |
expected controller behavior
```

The inference system must be testable without a human wearing electrodes.

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```
