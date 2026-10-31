/**
 * Fixed-capacity circular buffer of Float32 samples.
 * write() never grows the underlying storage.
 */
export class ChannelBuffer {
  constructor(capacity = 4096) {
    this.capacity = capacity | 0;
    this.data = new Float32Array(this.capacity);
    this.writeIdx = 0;
    this.count = 0;
    this.totalWritten = 0;
  }

  write(sample) {
    this.data[this.writeIdx] = sample;
    this.writeIdx = (this.writeIdx + 1) % this.capacity;
    if (this.count < this.capacity) this.count++;
    this.totalWritten++;
  }

  writeBlock(samples) {
    for (let i = 0; i < samples.length; i++) this.write(samples[i]);
  }

  /** Copy last n samples into out (Float32Array). Oldest → newest. */
  latest(n, out) {
    const take = Math.min(n, this.count);
    if (!out || out.length < take) out = new Float32Array(take);
    const start = (this.writeIdx - take + this.capacity) % this.capacity;
    for (let i = 0; i < take; i++) {
      out[i] = this.data[(start + i) % this.capacity];
    }
    return out.subarray(0, take);
  }

  /** Snapshot of entire valid region, oldest → newest. */
  snapshot() {
    return this.latest(this.count);
  }

  clear() {
    this.writeIdx = 0;
    this.count = 0;
    this.totalWritten = 0;
    this.data.fill(0);
  }

  get filled() {
    return this.count === this.capacity;
  }
}
