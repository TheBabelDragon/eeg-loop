# Architecture

```
+--------------------------+
|     SIGNAL PROCESSOR     |
|                          |
| audio                    |
| oscillators              |
| binaural processing      |
| isochronic processing    |
| modulation               |
+------------+-------------+
             |
             | stimulus
             v
        +----------+
        |  PERSON  |
        +----+-----+
             |
             | EEG
             v
+--------------------------+
|        EEG-LOOP          |
|                          |
| acquisition              |
|      |                   |
| signal quality           |
|      |                   |
| features                 |
|      |                   |
| individualized inference |
|      |                   |
| controller               |
+------------+-------------+
             |
             | new parameters
             +----------------> SIGNAL PROCESSOR
```

v0.1 implements only the left column of eeg-loop down through raw recording
and replay. Stimulus integration is v0.5.
