/**
 * Live signal analysis independent of the visual renderer.
 * Hann-windowed one-sided PSD. Does NOT interpret as medical/psych states.
 */
import { psd, bandPowerFromPsd, dominantFrequency } from "../utils/fft.js";
import { ArtifactDetector } from "./ArtifactDetector.js";

const BANDS = {
  delta: [0.5, 4], theta: [4, 8], alpha: [8, 13], beta: [13, 30], gamma: [30, 45],
};

export class SignalAnalyzer {
  constructor({ sampleRate = 250, windowSize = 512 } = {}) {
    this.sampleRate = sampleRate;
    this.windowSize = windowSize;
    this.detector = new ArtifactDetector();
    this.lastResult = null;
  }
  setSampleRate(sr) { this.sampleRate = sr; }

  analyze(xs) {
    if (!xs || xs.length < 16) return this._invalid("insufficient_samples");
    let sum = 0, sumSq = 0, min = Infinity, max = -Infinity;
    for (let i = 0; i < xs.length; i++) {
      const x = xs[i]; sum += x; sumSq += x * x;
      if (x < min) min = x; if (x > max) max = x;
    }
    const n = xs.length;
    const mean = sum / n;
    const variance = Math.max(0, sumSq / n - mean * mean);
    const rms = Math.sqrt(sumSq / n);
    const peakToPeak = max - min;
    const win = xs.length > this.windowSize ? xs.subarray(xs.length - this.windowSize) : xs;
    const { freqs, power, df } = psd(win, this.sampleRate);
    const domFreq = dominantFrequency(freqs, power, 0.5, 45);
    const bandPowers = {}; let total = 0;
    for (const [name, [lo, hi]] of Object.entries(BANDS)) {
      const p = bandPowerFromPsd(freqs, power, lo, hi);
      bandPowers[name] = p; total += p;
    }
    const rel = {};
    for (const k of Object.keys(bandPowers)) rel[k] = total > 0 ? bandPowers[k] / total : 0;
    const art = this.detector.detect(xs);
    const quality = Math.max(0, 1 - art.probability);
    let inferenceState = "VALID";
    if (art.probability >= 0.7) inferenceState = "NO_VALID_INFERENCE";
    else if (quality < 0.3) inferenceState = "LOW_QUALITY";
    const result = {
      rms, peakToPeak, mean, variance, dominantFrequency: domFreq,
      bandPowers, relativePowers: rel,
      artifactProbability: art.probability, artifactFlags: art.flags,
      quality, inferenceState, df, freqs, power, nSamples: n,
    };
    this.lastResult = result;
    return result;
  }

  _invalid(reason) {
    return {
      rms: 0, peakToPeak: 0, mean: 0, variance: 0, dominantFrequency: 0,
      bandPowers: { delta: 0, theta: 0, alpha: 0, beta: 0, gamma: 0 },
      relativePowers: { delta: 0, theta: 0, alpha: 0, beta: 0, gamma: 0 },
      artifactProbability: 1, artifactFlags: [reason], quality: 0,
      inferenceState: "NO_VALID_INFERENCE", df: 0,
      freqs: new Float64Array(0), power: new Float64Array(0), nSamples: 0,
    };
  }
}
