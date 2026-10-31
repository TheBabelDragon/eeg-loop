/**
 * Browser-side session recorder.
 * JSON Lines compatible with protocol/EEGStream.md spirit.
 * Immutable raw samples; derived analysis stored separately.
 */
export class SessionRecorder {
  constructor({ sampleRate = 250, channelCount = 4, channelNames = null } = {}) {
    this.sampleRate = sampleRate;
    this.channelCount = channelCount;
    this.channelNames = channelNames || Array.from({ length: channelCount }, (_, i) => `ch${i}`);
    this.recording = false;
    this.packets = [];
    this.header = null;
    this.analysisLog = [];
    this.sessionId = null;
    this._seq = 0;
    this._samplesPerPacket = 25;
    this._frameBuf = [];
  }

  start({ seed = null, source = "synthetic-browser" } = {}) {
    this.recording = true;
    this.packets = [];
    this.analysisLog = [];
    this._seq = 0;
    this._frameBuf = [];
    this.sessionId = `browser-${Date.now().toString(36)}`;
    this.header = {
      format: "eeg-loop.session",
      version: 2,
      session_id: this.sessionId,
      sample_rate: this.sampleRate,
      channel_count: this.channelCount,
      channel_names: this.channelNames,
      units: "normalized_sim",
      source,
      created_at: new Date().toISOString(),
      hardware_revision: null,
      firmware_revision: null,
      software_revision: "browser-lab-0.1",
      seed,
      simulated: true,
    };
  }

  pushFrame(frame, timestampUs) {
    if (!this.recording) return;
    this._frameBuf.push({ frame: Float32Array.from(frame), timestampUs });
    if (this._frameBuf.length >= this._samplesPerPacket) this._flushPacket();
  }

  _flushPacket() {
    if (this._frameBuf.length === 0) return;
    const samples = this._frameBuf.map((f) => Array.from(f.frame));
    const timestampUs = this._frameBuf[0].timestampUs;
    this.packets.push({
      sequence: this._seq++,
      timestamp_us: timestampUs,
      sample_rate: this.sampleRate,
      channel_count: this.channelCount,
      samples,
      status: 0,
      quality: 1.0,
    });
    this._frameBuf = [];
  }

  logAnalysis(result) {
    if (!this.recording) return;
    this.analysisLog.push({
      t: Date.now(),
      sequence: this._seq,
      rms: result.rms,
      artifact_probability: result.artifactProbability,
      inference_state: result.inferenceState,
      relative_powers: { ...result.relativePowers },
    });
  }

  stop() {
    if (!this.recording) return null;
    this._flushPacket();
    this.recording = false;
    return this.export();
  }

  export() {
    const rawLines = [JSON.stringify(this.header)];
    for (const p of this.packets) rawLines.push(JSON.stringify(p));
    const sampleCount = this.packets.reduce((a, p) => a + p.samples.length, 0);
    const finalization = {
      record_type: "finalization",
      session_id: this.sessionId,
      format: "eeg-loop.session",
      version: 2,
      packet_count: this.packets.length,
      sample_count: sampleCount,
      first_sequence: this.packets.length ? this.packets[0].sequence : null,
      last_sequence: this.packets.length ? this.packets[this.packets.length - 1].sequence : null,
      status: "finalized",
      simulated: true,
    };
    rawLines.push(JSON.stringify(finalization));
    return {
      rawJsonl: rawLines.join("\n") + "\n",
      derived: { session_id: this.sessionId, analysis: this.analysisLog },
      meta: {
        sessionId: this.sessionId,
        packetCount: this.packets.length,
        sampleCount,
        sampleRate: this.sampleRate,
        channelCount: this.channelCount,
        seed: this.header.seed,
        simulated: true,
      },
    };
  }
}

export class SessionPlayer {
  constructor() {
    this.packets = [];
    this.header = null;
  }

  load(rawJsonl) {
    const lines = rawJsonl.trim().split("\n");
    this.header = JSON.parse(lines[0]);
    this.packets = [];
    for (let i = 1; i < lines.length; i++) {
      const obj = JSON.parse(lines[i]);
      if (obj.record_type === "finalization") continue;
      this.packets.push(obj);
    }
    return this.header;
  }

  *frames() {
    for (const pkt of this.packets) {
      for (let i = 0; i < pkt.samples.length; i++) {
        yield {
          frame: Float32Array.from(pkt.samples[i]),
          timestampUs: pkt.timestamp_us + Math.round((i / pkt.sample_rate) * 1e6),
        };
      }
    }
  }
}
