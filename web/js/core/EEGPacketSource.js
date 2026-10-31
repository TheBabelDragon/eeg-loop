/**
 * EEGPacketSource — protocol/EEGStream.md adapter for the browser lab.
 *
 * Decodes immutable session JSONL (v1 or v2) and pushes per-sample frames
 * through the same SignalSource.onFrame callback used by SyntheticEEGSource.
 * Visualization and analysis layers stay unchanged.
 *
 * Does not open hardware, WebSerial, or WebUSB. File / string only.
 * Gaps, duplicates, and non-finite samples are reported; never auto-repaired.
 */
import { SignalSource } from "./SignalSource.js";

/**
 * Parse an eeg-loop.session JSONL string into header + packets.
 * Skips finalization records. Does not invent samples.
 *
 * @param {string} rawJsonl
 * @returns {{ header: object, packets: object[], diagnostics: string[] }}
 */
export function parseSessionJsonl(rawJsonl) {
  const diagnostics = [];
  if (typeof rawJsonl !== "string" || !rawJsonl.trim()) {
    throw new Error("empty session payload");
  }
  const lines = rawJsonl.trim().split("\n");
  let header;
  try {
    header = JSON.parse(lines[0]);
  } catch {
    throw new Error("session header is not valid JSON");
  }
  if (header.format && header.format !== "eeg-loop.session") {
    diagnostics.push(`unexpected format: ${header.format}`);
  }
  const packets = [];
  let prevSeq = null;
  let prevTs = null;
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    let obj;
    try {
      obj = JSON.parse(line);
    } catch {
      diagnostics.push(`line ${i + 1}: invalid JSON`);
      continue;
    }
    if (obj.record_type === "finalization") continue;
    if (!Array.isArray(obj.samples) || obj.samples.length === 0) {
      diagnostics.push(`seq ${obj.sequence}: empty packet rejected`);
      continue;
    }
    if (prevSeq !== null) {
      if (obj.sequence === prevSeq) diagnostics.push(`duplicate sequence ${obj.sequence}`);
      else if (obj.sequence !== prevSeq + 1) {
        diagnostics.push(`sequence gap ${prevSeq} → ${obj.sequence}`);
      }
    }
    if (prevTs !== null && obj.timestamp_us < prevTs) {
      diagnostics.push(`backward timestamp at seq ${obj.sequence}`);
    }
    if (prevTs !== null && obj.timestamp_us === prevTs) {
      diagnostics.push(`repeated timestamp at seq ${obj.sequence}`);
    }
    for (const row of obj.samples) {
      for (const v of row) {
        if (!Number.isFinite(v)) {
          diagnostics.push(`seq ${obj.sequence}: non-finite sample`);
          break;
        }
      }
    }
    packets.push(obj);
    prevSeq = obj.sequence;
    prevTs = obj.timestamp_us;
  }
  return { header, packets, diagnostics };
}

/**
 * Replay a recorded session as a SignalSource.
 * Clock is independent of requestAnimationFrame (setInterval catch-up).
 */
export class EEGPacketSource extends SignalSource {
  /**
   * @param {object} opts
   * @param {string} [opts.rawJsonl] — session JSONL
   * @param {(frame: Float32Array, timestampUs: number) => void} [opts.onFrame]
   * @param {boolean} [opts.loop=false]
   * @param {number} [opts.playbackRate=1] — 1 = real-time vs sample_rate
   */
  constructor(opts = {}) {
    const parsed = opts.rawJsonl ? parseSessionJsonl(opts.rawJsonl) : null;
    const header = parsed?.header ?? {};
    const channelCount = header.channel_count ?? opts.channelCount ?? 4;
    const sampleRate = header.sample_rate ?? opts.sampleRate ?? 250;
    super({
      sampleRate,
      channelCount,
      onFrame: opts.onFrame,
    });
    this.header = header;
    this.packets = parsed?.packets ?? [];
    this.diagnostics = parsed?.diagnostics ?? [];
    this.loop = opts.loop ?? false;
    this.playbackRate = opts.playbackRate ?? 1;
    this.simulated = header.simulated === true || header.source === "synthetic-browser";
    this._frames = null;
    this._cursor = 0;
    this._timer = null;
    this._t0 = 0;
    this._buildFrameList();
  }

  _buildFrameList() {
    this._frames = [];
    for (const pkt of this.packets) {
      const sr = pkt.sample_rate || this.sampleRate;
      for (let i = 0; i < pkt.samples.length; i++) {
        const row = pkt.samples[i];
        const n = Math.min(this.channelCount, row.length);
        const frame = new Float32Array(this.channelCount);
        for (let c = 0; c < n; c++) frame[c] = row[c];
        const timestampUs =
          (pkt.timestamp_us ?? 0) + Math.round((i / sr) * 1e6);
        this._frames.push({ frame, timestampUs });
      }
    }
  }

  load(rawJsonl) {
    const { header, packets, diagnostics } = parseSessionJsonl(rawJsonl);
    this.header = header;
    this.packets = packets;
    this.diagnostics = diagnostics;
    this.sampleRate = header.sample_rate ?? this.sampleRate;
    this.channelCount = header.channel_count ?? this.channelCount;
    this.simulated =
      header.simulated === true || header.source === "synthetic-browser";
    this._cursor = 0;
    this.sampleIndex = 0;
    this._buildFrameList();
    return { header, diagnostics, frameCount: this._frames.length };
  }

  get frameCount() {
    return this._frames?.length ?? 0;
  }

  get exhausted() {
    return this._cursor >= (this._frames?.length ?? 0);
  }

  _tick() {
    if (!this.running) return;
    const now = performance.now();
    const elapsed = ((now - this._t0) / 1000) * this.playbackRate;
    const targetIndex = Math.floor(elapsed * this.sampleRate);
    while (this._cursor < targetIndex && this._cursor < this._frames.length) {
      const { frame, timestampUs } = this._frames[this._cursor];
      this.emit(frame, timestampUs);
      this._cursor++;
    }
    if (this._cursor >= this._frames.length) {
      if (this.loop && this._frames.length > 0) {
        this._cursor = 0;
        this.sampleIndex = 0;
        this._t0 = performance.now();
      } else {
        this.stop();
      }
    }
  }

  start() {
    if (this.running) return;
    if (!this._frames || this._frames.length === 0) {
      throw new Error("EEGPacketSource: no frames loaded");
    }
    this.running = true;
    if (this._cursor >= this._frames.length) this._cursor = 0;
    this._t0 =
      performance.now() - (this._cursor / this.sampleRate) * 1000 / this.playbackRate;
    const intervalMs = Math.max(4, Math.floor(1000 / this.sampleRate));
    this._timer = setInterval(() => this._tick(), intervalMs);
  }

  stop() {
    this.running = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }

  /** Immediate full dump (tests / offline batch). */
  *frames() {
    for (const f of this._frames) yield f;
  }
}
