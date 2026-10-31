/**
 * Abstract signal source interface.
 *
 * A concrete source pushes Float32 sample frames (one per channel) at a
 * fixed sample rate. The visualization layer never cares whether the
 * source is synthetic or a future EEGPacketSource adapter.
 *
 * Future real-side integration: implement EEGPacketSource that decodes
 * protocol/EEGStream.md packets and calls the same onFrame callback.
 */
export class SignalSource {
  /**
   * @param {object} opts
   * @param {number} opts.sampleRate
   * @param {number} opts.channelCount
   * @param {(frame: Float32Array, timestampUs: number) => void} opts.onFrame
   */
  constructor({ sampleRate = 250, channelCount = 4, onFrame = null } = {}) {
    this.sampleRate = sampleRate;
    this.channelCount = channelCount;
    this.onFrame = onFrame;
    this.running = false;
    this.sampleIndex = 0;
  }

  start() {
    throw new Error("SignalSource.start() not implemented");
  }

  stop() {
    throw new Error("SignalSource.stop() not implemented");
  }

  /** Optional: push one frame of channelCount samples. */
  emit(frame, timestampUs) {
    if (this.onFrame) this.onFrame(frame, timestampUs);
    this.sampleIndex++;
  }
}
