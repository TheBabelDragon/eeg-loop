/**
 * Packet encoder: EEG sample block → binary DATA payload.
 *
 * Layout matches host/acquisition/packet_codec.py exactly so host and
 * firmware stay synchronized. See protocol/EEGStream.md.
 */

#ifndef EEG_PACKET_ENCODER_H
#define EEG_PACKET_ENCODER_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EEG_PKT_HEADER_SIZE  26
#define EEG_PKT_MAX_CHANNELS 8
#define EEG_PKT_MAX_SAMPLES  64

typedef struct {
    uint32_t sequence;
    uint64_t timestamp_us;
    float    sample_rate;
    uint16_t channel_count;
    uint16_t n_samples;
    uint32_t status;
    float    quality;          /* [0, 1] */
    float    samples[EEG_PKT_MAX_SAMPLES][EEG_PKT_MAX_CHANNELS];
} eeg_packet_t;

/**
 * Encode packet into buffer. Returns bytes written, or -1 on error.
 * buffer must be at least EEG_PKT_HEADER_SIZE + n_samples * channel_count * 4.
 */
int eeg_packet_encode(const eeg_packet_t *pkt, uint8_t *buffer, size_t buffer_len);

/**
 * Decode buffer into packet. Returns 0 on success, -1 on error.
 */
int eeg_packet_decode(const uint8_t *buffer, size_t buffer_len, eeg_packet_t *pkt);

#ifdef __cplusplus
}
#endif

#endif /* EEG_PACKET_ENCODER_H */
