# Conceptual BOM

Initial, not frozen. Do not treat this as a buy list for a finished device.

| Item | Role |
| --- | --- |
| Ag/AgCl EEG electrodes | Skin interface, passive only |
| Electrode leads / connectors | Analog path to AFE |
| ADS1299-based acquisition board | Low-level biopotential AFE |
| ESP32-S3 development board | SPI master, timestamp, USB |
| Isolated / battery-powered host arrangement | Avoid mains-referenced electrode path |
| Input protection components | As required by the chosen AFE topology |
| Enclosure / headband / mechanical mounting | Strain relief and electrode placement |

PCB files in `hardware/pcb/` stay empty until the acquisition architecture is validated on a development board.
