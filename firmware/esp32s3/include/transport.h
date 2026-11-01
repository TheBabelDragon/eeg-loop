/**
 * USB serial transport framing (matches host/acquisition/framing.py).
 */

#ifndef EEG_TRANSPORT_H
#define EEG_TRANSPORT_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EEG_FRAME_MAGIC_0     0xA5
#define EEG_FRAME_MAGIC_1     0x5A
#define EEG_PROTOCOL_VERSION  1
#define EEG_FRAME_HEADER_SIZE 6
#define EEG_FRAME_CRC_SIZE    2
#define EEG_FRAME_MAX_PAYLOAD 4096

#define EEG_FRAME_HANDSHAKE_REQ  0x01
#define EEG_FRAME_HANDSHAKE_ACK  0x02
#define EEG_FRAME_DATA           0x10
#define EEG_FRAME_STATUS         0x20
#define EEG_FRAME_ERROR          0x30

uint16_t eeg_crc16_ccitt(const uint8_t *data, size_t len);

/**
 * Encode a frame into out. Returns total bytes, or -1 on error.
 * out_len must be >= HEADER + payload_len + CRC.
 */
int eeg_frame_encode(uint8_t frame_type, const uint8_t *payload, size_t payload_len,
                     uint8_t *out, size_t out_len);

#ifdef __cplusplus
}
#endif

#endif /* EEG_TRANSPORT_H */
