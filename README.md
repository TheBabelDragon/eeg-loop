# eeg-loop

Open EEG acquisition and closed-loop signal platform for the Signal Processor ecosystem.

https://github.com/TheBabelDragon/eeg-loop

This repository is the observation + inference + adaptation side.
[signal-processor](https://github.com/TheBabelDragon/signal-processor) remains the browser / audio stimulus engine.

The first deployment does **not** stimulate the body. It passively acquires EEG, records it, characterizes it, and exposes a stable data protocol. Closed-loop audio comes only after acquisition and signal-quality validation.

## Safety

This project is an experimental EEG acquisition and signal-processing platform.
It is not a medical device and does not provide medical diagnosis or treatment.
The EEG interface is intended for passive sensing.
Do not connect the electrode interface to mains-referenced equipment or to stimulation circuitry.
Any eventual human-subject experimentation must use appropriate electrical isolation, current limiting, electrode/interface design, and applicable research and safety procedures.

The EEG sensing path and stimulation path remain separate systems.

Do not combine the EEG electrode path with TENS/EMS stimulation hardware.
Adhesive pads may be reused as passive electrodes only if appropriate; stimulation circuitry stays completely outside this repository.

## Layers

```
HARDWARE
   |
ACQUISITION
   |
INFERENCE
   |
CONTROL
```

Eventual complete loop:

```
Signal Processor
      |
      | audio stimulus
      v
   headphones
      |
      v
    subject
      |
      | EEG
      v
 ADS1299 / AFE
      |
      v
  ESP32-S3
      |
      v
 host acquisition
      |
      v
 signal processing
      |
      v
 inference
      |
      v
 controller
      |
      +----------------> Signal Processor
```

eeg-loop is a **passive sensing system**.

## Hardware target

```
Ag/AgCl electrodes
        |
EEG analog front end
        |
ADS1299
        | SPI
ESP32-S3
        | USB
Linux host
```

First prototype: 1-2 active EEG channels + reference + bias/common-mode as required by the AFE.
Do not start with an eight-channel finished headset.

First hardware milestone: acquire a believable differential biopotential waveform and prove the signal path.

## Data rule

```
RAW
 |
immutable session
 |
derived processing
```

Never overwrite the only copy with a filtered version.

A recorded session must replay through the same processing, inference, and controller pipelines without hardware attached.

Protocol: [`protocol/EEGStream.md`](protocol/EEGStream.md)

## Host tools

```bash
python3 -m host.tools.eeg_record --device /dev/ttyACM0 --output session-001.eeg
python3 -m host.tools.eeg_inspect session-001.eeg
python3 -m host.tools.eeg_replay session-001.eeg
python3 -m host.tools.eeg_export session-001.eeg --format csv
```

`eeg-record` is a USB serial stub until firmware streams `EEGPacket` frames.
`eeg-inspect` / `eeg-replay` / `eeg-export` already run against the session format (including synthetic fixtures).

## Measurement is not interpretation

v0 inference reports measurements (`FeatureVector`) and relative deviation from an individual baseline (`StateVector`).
It does not label focus, happiness, consciousness, or relaxation.

If artifacts dominate, the system must be allowed to say:

```
NO VALID INFERENCE
artifact_probability = 0.94
```

## Integration

```
signal-processor  = stimulus engine
eeg-loop          = feedback engine
```

Do not commit to WebSocket / WebSerial / WebUSB / local bridge until the acquisition protocol is stable.

Thesis: do not build an EEG headset that tells you what your brain is doing. Build a minimal EEG interface that lets an adaptive system observe its own effect on a person and change the stimulus accordingly.

## Milestones

### v0.1 — Acquisition (current scaffold)

- [ ] ADS1299 acquisition working
- [ ] ESP32-S3 streaming
- [x] protocol documented
- [x] sequence / timestamp / sample-rate fields defined
- [x] raw recording format
- [x] replay path
- [x] basic inspection metrics
- [x] documented hardware intent
- [ ] live USB stream validated on hardware

### v0.2 — Signal Analysis

- [ ] artifact detection
- [ ] filtering pipeline
- [ ] PSD
- [ ] spectral features
- [ ] baseline calculation
- [ ] replayable analysis

### v0.3 — Inference

- [ ] FeatureVector
- [ ] StateVector
- [ ] confidence
- [ ] individualized baseline
- [ ] model / replay framework
- [ ] deterministic tests

### v0.4 — Closed Loop

- [ ] controller interface
- [ ] stimulus parameter interface
- [ ] perturbation experiments
- [ ] response measurement
- [ ] parameter constraints
- [ ] fail-safe invalid-state behavior
- [ ] offline controller simulation

### v0.5 — Signal Processor Integration

Only after v0.1-v0.4 work.

## Layout

```
eeg-loop/
|-- firmware/esp32s3/     # configure AFE, sample, timestamp, USB
|-- hardware/             # schematics, PCB, BOM — not a medical device
|-- host/eeg-stream/      # immutable session I/O
|-- host/tools/           # record / inspect / replay / export
|-- inference/            # features, artifacts, models
|-- control/              # stimulus parameters from state + target
|-- protocol/             # EEGStream
|-- experiments/          # reproducible session records
|-- tests/
|-- tools/
|-- web/                  # browser EEG laboratory (synthetic, offline)
`-- docs/
```

## Browser EEG Laboratory

Experimental offline visualization lab under [`web/`](web/).

```bash
cd web && python3 -m http.server 8765
# open http://localhost:8765/
```

Synthetic multi-channel EEG generator, oscilloscope, live spectrum, artifact injection, session record/export/replay. All signals are **SIMULATED**. No medical claims, no real hardware I/O.

See [`web/README.md`](web/README.md) for architecture and the future `EEGPacketSource` adapter boundary (preserves `protocol/EEGStream.md`).

## License

MIT
