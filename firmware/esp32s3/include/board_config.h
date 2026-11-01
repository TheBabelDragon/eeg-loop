/**
 * Board-specific pin configuration for ESP32-S3 + ADS1299.
 *
 * DO NOT invent GPIO assignments. Values below are PLACEHOLDERS that must
 * be replaced with the actual wiring for the development board in use.
 *
 * Document the physical mapping in hardware/README.md and this file before
 * claiming hardware functionality.
 *
 * Reference (unverified until board is wired):
 *   Typical ESP32-S3 DevKit SPI2 (FSPI) pins — CONFIRM ON YOUR BOARD.
 */

#ifndef EEG_BOARD_CONFIG_H
#define EEG_BOARD_CONFIG_H

/* SPI host for ADS1299 */
#define EEG_SPI_HOST           SPI2_HOST

/* Placeholder GPIOs — replace with documented board wiring */
#define EEG_PIN_SPI_SCLK       (-1)   /* e.g. GPIO12 — NOT WIRED */
#define EEG_PIN_SPI_MOSI       (-1)   /* e.g. GPIO11 — NOT WIRED */
#define EEG_PIN_SPI_MISO       (-1)   /* e.g. GPIO13 — NOT WIRED */
#define EEG_PIN_ADS_CS         (-1)   /* chip select */
#define EEG_PIN_ADS_DRDY       (-1)   /* data-ready (input, interrupt) */
#define EEG_PIN_ADS_START      (-1)   /* START pin (optional, can be soft-start) */
#define EEG_PIN_ADS_RESET      (-1)   /* RESET pin */

/* USB serial is the built-in USB-Serial/JTAG or UART0 CDC on ESP32-S3 */
#define EEG_UART_BAUD          921600

/* Acquisition defaults (overridable via handshake) */
#define EEG_DEFAULT_SAMPLE_RATE_HZ   250
#define EEG_DEFAULT_CHANNEL_COUNT    2
#define EEG_SAMPLES_PER_PACKET       25

/* Compile-time guard: refuse to build a "hardware" binary with placeholder pins */
#if (EEG_PIN_SPI_SCLK < 0) || (EEG_PIN_ADS_CS < 0) || (EEG_PIN_ADS_DRDY < 0)
#  define EEG_HARDWARE_PINS_CONFIGURED  0
#else
#  define EEG_HARDWARE_PINS_CONFIGURED  1
#endif

#endif /* EEG_BOARD_CONFIG_H */
