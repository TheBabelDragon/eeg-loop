/**
 * Coarse artifact detector — mirrors the spirit of inference/features/extract.py
 * artifact_probability. Not a clinical detector.
 */
export class ArtifactDetector {
  /**
   * @param {Float32Array|number[]} xs
   * @returns {{ probability: number, flags: string[] }}
   */
  detect(xs) {
    if (!xs || xs.length < 8) {
      return { probability: 1.0, flags: ["too_short"] };
    }
    let sum = 0, sumSq = 0, peak = 0;
    for (let i = 0; i < xs.length; i++) {
      const x = xs[i];
      sum += x;
      sumSq += x * x;
      const a = Math.abs(x);
      if (a > peak) peak = a;
    }
    const n = xs.length;
    const mean = sum / n;
    const variance = sumSq / n - mean * mean;
    const rms = Math.sqrt(Math.max(0, variance + mean * mean));
    const flags = [];
    let score = 0;

    if (rms > 1e-12 && peak / rms > 8) {
      score += 0.4;
      flags.push("high_crest");
    }
    if (variance > 1e-12 && Math.abs(mean) / Math.sqrt(variance) > 3) {
      score += 0.2;
      flags.push("dc_offset");
    }
    let maxDiff = 0, sumDiff = 0;
    for (let i = 1; i < n; i++) {
      const d = Math.abs(xs[i] - xs[i - 1]);
      sumDiff += d;
      if (d > maxDiff) maxDiff = d;
    }
    const meanDiff = sumDiff / (n - 1);
    if (meanDiff > 1e-12 && maxDiff > 8 * meanDiff) {
      score += 0.3;
      flags.push("transient");
    }
    if (rms < 1e-4) {
      score += 0.5;
      flags.push("flatline");
    }

    return { probability: Math.min(1, score), flags };
  }
}
