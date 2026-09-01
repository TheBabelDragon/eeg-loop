# ESP32-S3 EEG Firmware

Responsibilities:

- configure EEG AFE
- acquire samples
- maintain sample sequence
- timestamp frames
- transmit acquisition data

The firmware does not perform inference.

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

`src/` and `include/` are reserved for the first ADS1299 bring-up.
Do not add closed-loop or brain-state code here.
