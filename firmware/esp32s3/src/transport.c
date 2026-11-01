#include "transport.h"

uint16_t eeg_crc16_ccitt(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            if (crc & 0x8000) {
                crc = (uint16_t)((crc << 1) ^ 0x1021);
            } else {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

int eeg_frame_encode(uint8_t frame_type, const uint8_t *payload, size_t payload_len,
                     uint8_t *out, size_t out_len) {
    if (!out) return -1;
    if (payload_len > EEG_FRAME_MAX_PAYLOAD) return -1;
    size_t total = EEG_FRAME_HEADER_SIZE + payload_len + EEG_FRAME_CRC_SIZE;
    if (out_len < total) return -1;

    out[0] = EEG_FRAME_MAGIC_0;
    out[1] = EEG_FRAME_MAGIC_1;
    out[2] = EEG_PROTOCOL_VERSION;
    out[3] = frame_type;
    out[4] = (uint8_t)(payload_len & 0xFF);
    out[5] = (uint8_t)((payload_len >> 8) & 0xFF);
    if (payload_len && payload) {
        for (size_t i = 0; i < payload_len; i++) {
            out[6 + i] = payload[i];
        }
    }
    /* CRC over version..payload */
    uint16_t crc = eeg_crc16_ccitt(out + 2, 4 + payload_len);
    out[6 + payload_len]     = (uint8_t)(crc & 0xFF);
    out[6 + payload_len + 1] = (uint8_t)((crc >> 8) & 0xFF);
    return (int)total;
}
