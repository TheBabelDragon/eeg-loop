# EEG Hardware

Passive EEG acquisition hardware for eeg-loop.

Initial target:

Electrodes -> EEG AFE / ADS1299 -> ESP32-S3 -> USB

The hardware is intended for signal acquisition and experimentation.
It is not a medical device.

## Boundary

The EEG system is a passive sensing system.

Do not combine the EEG electrode path with TENS/EMS stimulation hardware.
Stimulation circuitry stays completely outside this repository.

Power the acquisition path from battery / isolated supply. Do not attach
electrodes to mains-referenced equipment.

## First prototype

- Ag/AgCl electrodes
- ADS1299-based analog front end
- ESP32-S3 development board
- 1-2 active EEG channels + reference + bias / common-mode as required
- USB to a Linux host

Do not immediately attempt an eight-channel finished headset.
Do not finalize the PCB until the acquisition architecture is validated.

First hardware milestone: acquire a believable differential biopotential
waveform and prove that the entire signal path works.
