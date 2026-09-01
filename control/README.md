# Controller

Consumes:

- current state
- target
- constraints
- previous stimulus

Produces:

- next stimulus parameters

```
State + Target
      |
  Controller
      |
StimulusParameters
```

Example:

```
target:
    maximize individualized feature X
constraints:
    maximum permitted audio level
    maximum parameter excursion
    maximum adaptation rate
output:
    carrier_frequency
    modulation_frequency
    modulation_depth
    gain
```

## Start with perturbation, not a giant model

```
stimulus A -> measure response
stimulus B -> measure response
stimulus C -> measure response
```

Estimate the map from stimulus parameters to measured response.
First closed-loop algorithm:

```
perturb
measure
compare
retain/reject
repeat
```

Invalid EEG state -> fail-safe: do not adapt, hold last safe parameters or idle.

The controller talks to [signal-processor](https://github.com/TheBabelDragon/signal-processor).
Do not commit the transport (WebSocket / WebSerial / WebUSB / bridge) until EEGStream is stable.

Audio closed-loop is **not** part of v0.1. Acquisition and signal quality come first.
