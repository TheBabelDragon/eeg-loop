/**
 * Real FFT (radix-2 Cooley-Tukey) for power-of-two lengths.
 */
export function nextPow2(n) {
  let p = 1;
  while (p < n) p <<= 1;
  return p;
}

export function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const half = len >> 1;
    const ang = (-2 * Math.PI) / len;
    const wRe = Math.cos(ang);
    const wIm = Math.sin(ang);
    for (let i = 0; i < n; i += len) {
      let curRe = 1, curIm = 0;
      for (let j = 0; j < half; j++) {
        const uRe = re[i + j], uIm = im[i + j];
        const vRe = re[i + j + half] * curRe - im[i + j + half] * curIm;
        const vIm = re[i + j + half] * curIm + im[i + j + half] * curRe;
        re[i + j] = uRe + vRe;
        im[i + j] = uIm + vIm;
        re[i + j + half] = uRe - vRe;
        im[i + j + half] = uIm - vIm;
        const nRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = nRe;
      }
    }
  }
}

export function hann(n) {
  const w = new Float64Array(n);
  for (let i = 0; i < n; i++) w[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1)));
  return w;
}

/** One-sided PSD. Scale |X|^2 / (sum(w^2)*fs). df = fs/N. */
export function psd(xs, sampleRate, { pad = true } = {}) {
  const n0 = xs.length;
  if (n0 < 4 || sampleRate <= 0) return { freqs: new Float64Array(0), power: new Float64Array(0), df: 0 };
  const n = pad ? nextPow2(n0) : n0;
  const re = new Float64Array(n);
  const im = new Float64Array(n);
  const w = hann(n0);
  let wss = 0;
  for (let i = 0; i < n0; i++) { re[i] = xs[i] * w[i]; wss += w[i] * w[i]; }
  fft(re, im);
  const half = (n >> 1) + 1;
  const freqs = new Float64Array(half);
  const power = new Float64Array(half);
  const scale = 1 / (wss * sampleRate);
  for (let k = 0; k < half; k++) {
    freqs[k] = (k * sampleRate) / n;
    const p = (re[k] * re[k] + im[k] * im[k]) * scale;
    power[k] = k === 0 || k === half - 1 ? p : 2 * p;
  }
  return { freqs, power, df: sampleRate / n };
}

export function bandPowerFromPsd(freqs, power, lo, hi) {
  let acc = 0;
  for (let i = 0; i < freqs.length; i++) if (freqs[i] >= lo && freqs[i] < hi) acc += power[i];
  const df = freqs.length > 1 ? freqs[1] - freqs[0] : 1;
  return acc * df;
}

export function dominantFrequency(freqs, power, fMin = 0.5, fMax = 45) {
  let best = 0, bestP = -1;
  for (let i = 0; i < freqs.length; i++) {
    if (freqs[i] < fMin || freqs[i] > fMax) continue;
    if (power[i] > bestP) { bestP = power[i]; best = freqs[i]; }
  }
  return best;
}
