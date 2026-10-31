/**
 * Deterministic, seeded synthetic EEG generator.
 * All output is SIMULATED — never presented as real physiological data.
 * Generation clock is independent of requestAnimationFrame.
 */
import { SignalSource } from "./SignalSource.js";
import { mulberry32, gaussian } from "../utils/rng.js";

const BANDS = {
  delta: { lo: 0.5, hi: 4.0 },
  theta: { lo: 4.0, hi: 8.0 },
  alpha: { lo: 8.0, hi: 13.0 },
  beta:  { lo: 13.0, hi: 30.0 },
  gamma: { lo: 30.0, hi: 45.0 },
};

export class SyntheticEEGSource extends SignalSource {
  constructor(opts = {}) {
    super(opts);
    this.seed = opts.seed ?? 42;
    this.rng = mulberry32(this.seed);
    this.bandAmps = {
      delta: opts.delta ?? 0.25,
      theta: opts.theta ?? 0.35,
      alpha: opts.alpha ?? 0.70,
      beta:  opts.beta  ?? 0.30,
      gamma: opts.gamma ?? 0.12,
    };
    this.masterAmp = opts.masterAmp ?? 1.0;
    this.noiseLevel = opts.noise ?? 0.08;
    this.lineFreq = opts.lineFreq ?? 60;
    this.lineAmp = 0;
    this.driftAmp = opts.drift ?? 0.04;
    this.chPhase = [];
    this.chFreqJitter = [];
    this.chGain = [];
    for (let c = 0; c < this.channelCount; c++) {
      this.chPhase.push({
        delta: this.rng() * Math.PI * 2,
        theta: this.rng() * Math.PI * 2,
        alpha: this.rng() * Math.PI * 2,
        beta:  this.rng() * Math.PI * 2,
        gamma: this.rng() * Math.PI * 2,
      });
      this.chFreqJitter.push({
        delta: 0.9 + this.rng() * 0.2,
        theta: 0.9 + this.rng() * 0.2,
        alpha: 0.9 + this.rng() * 0.2,
        beta:  0.9 + this.rng() * 0.2,
        gamma: 0.9 + this.rng() * 0.2,
      });
      this.chGain.push(0.85 + this.rng() * 0.3);
    }
    this.artifacts = {
      blink: { active: false, t: 0, dur: 0, amp: 0, ch: 0 },
      muscle: { active: false, t: 0, dur: 0, amp: 0 },
      disconnect: { active: false, ch: -1 },
      spike: { pending: false, ch: 0, amp: 0 },
    };
    this._timer = null;
    this._t0 = 0;
  }

  setSeed(seed) {
    this.seed = seed >>> 0;
    this.rng = mulberry32(this.seed);
    for (let c = 0; c < this.channelCount; c++) {
      this.chPhase[c] = {
        delta: this.rng() * Math.PI * 2,
        theta: this.rng() * Math.PI * 2,
        alpha: this.rng() * Math.PI * 2,
        beta:  this.rng() * Math.PI * 2,
        gamma: this.rng() * Math.PI * 2,
      };
      this.chFreqJitter[c] = {
        delta: 0.9 + this.rng() * 0.2,
        theta: 0.9 + this.rng() * 0.2,
        alpha: 0.9 + this.rng() * 0.2,
        beta:  0.9 + this.rng() * 0.2,
        gamma: 0.9 + this.rng() * 0.2,
      };
      this.chGain[c] = 0.85 + this.rng() * 0.3;
    }
    this.sampleIndex = 0;
  }

  setBandAmps(amps) { Object.assign(this.bandAmps, amps); }
  setMasterAmp(v) { this.masterAmp = v; }
  setNoise(v) { this.noiseLevel = v; }
  setLineAmp(v) { this.lineAmp = v; }
  setLineFreq(f) { this.lineFreq = f; }

  injectBlink(channel = 0, amp = 3.5) {
    const a = this.artifacts.blink;
    a.active = true; a.t = 0;
    a.dur = 0.18 + this.rng() * 0.12;
    a.amp = amp; a.ch = channel % this.channelCount;
  }
  injectMuscle(duration = 0.4, amp = 1.8) {
    const a = this.artifacts.muscle;
    a.active = true; a.t = 0; a.dur = duration; a.amp = amp;
  }
  injectDisconnect(channel = 0) {
    this.artifacts.disconnect.active = true;
    this.artifacts.disconnect.ch = channel % this.channelCount;
  }
  clearDisconnect() {
    this.artifacts.disconnect.active = false;
    this.artifacts.disconnect.ch = -1;
  }
  injectSpike(channel = 0, amp = 5) {
    this.artifacts.spike.pending = true;
    this.artifacts.spike.ch = channel % this.channelCount;
    this.artifacts.spike.amp = amp;
  }
  injectLineNoise(amp = 0.35) { this.lineAmp = amp; }

  _centerFreq(band) {
    return (BANDS[band].lo + BANDS[band].hi) / 2;
  }

  _sampleChannel(c, t) {
    const ph = this.chPhase[c];
    const jt = this.chFreqJitter[c];
    let s = 0;
    for (const [name, amp] of Object.entries(this.bandAmps)) {
      if (amp <= 0) continue;
      const f0 = this._centerFreq(name) * jt[name];
      const am = 1 + 0.15 * Math.sin(2 * Math.PI * 0.3 * t + ph[name]);
      s += amp * am * Math.sin(2 * Math.PI * f0 * t + ph[name]);
      s += amp * 0.25 * Math.sin(2 * Math.PI * (f0 * 1.15) * t + ph[name] * 1.3);
    }
    s += this.driftAmp * Math.sin(2 * Math.PI * 0.07 * t + ph.delta);
    s += this.noiseLevel * gaussian(this.rng);
    if (this.lineAmp > 0) s += this.lineAmp * Math.sin(2 * Math.PI * this.lineFreq * t);
    const blink = this.artifacts.blink;
    if (blink.active && blink.ch === c) {
      const u = blink.t / blink.dur;
      s += blink.amp * Math.sin(Math.PI * u) * Math.exp(-3 * u);
    }
    const muscle = this.artifacts.muscle;
    if (muscle.active) s += muscle.amp * gaussian(this.rng) * (1 - muscle.t / muscle.dur);
    if (this.artifacts.disconnect.active && this.artifacts.disconnect.ch === c) {
      s = this.noiseLevel * 0.3 * gaussian(this.rng);
    }
    if (this.artifacts.spike.pending && this.artifacts.spike.ch === c) {
      s += this.artifacts.spike.amp;
      this.artifacts.spike.pending = false;
    }
    return s * this.masterAmp * this.chGain[c];
  }

  _advanceArtifacts(dt) {
    const blink = this.artifacts.blink;
    if (blink.active) { blink.t += dt; if (blink.t >= blink.dur) blink.active = false; }
    const muscle = this.artifacts.muscle;
    if (muscle.active) { muscle.t += dt; if (muscle.t >= muscle.dur) muscle.active = false; }
  }

  _tick() {
    if (!this.running) return;
    const now = performance.now();
    const elapsed = (now - this._t0) / 1000;
    const dt = 1 / this.sampleRate;
    const targetIndex = Math.floor(elapsed * this.sampleRate);
    while (this.sampleIndex < targetIndex) {
      const t = this.sampleIndex / this.sampleRate;
      const frame = new Float32Array(this.channelCount);
      for (let c = 0; c < this.channelCount; c++) frame[c] = this._sampleChannel(c, t);
      this._advanceArtifacts(dt);
      this.emit(frame, Math.round(t * 1e6));
    }
  }

  start() {
    if (this.running) return;
    this.running = true;
    this._t0 = performance.now() - (this.sampleIndex / this.sampleRate) * 1000;
    const intervalMs = Math.max(4, Math.floor(1000 / this.sampleRate));
    this._timer = setInterval(() => this._tick(), intervalMs);
  }

  stop() {
    this.running = false;
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  }

  generateBlock(nFrames) {
    const out = [];
    const dt = 1 / this.sampleRate;
    for (let i = 0; i < nFrames; i++) {
      const t = this.sampleIndex / this.sampleRate;
      const frame = new Float32Array(this.channelCount);
      for (let c = 0; c < this.channelCount; c++) frame[c] = this._sampleChannel(c, t);
      this._advanceArtifacts(dt);
      out.push(frame);
      this.sampleIndex++;
    }
    return out;
  }
}

export { BANDS };
