/**
 * Live FFT spectrum view with band regions.
 */
const CHANNEL_COLORS = [
  "#3d9cf0", "#3ecf8e", "#e0a84c", "#c77dff",
  "#f07178", "#56b6c2", "#d19a66", "#98c379",
];

const BAND_REGIONS = [
  { name: "δ", lo: 0.5, hi: 4, color: "rgba(107,140,174,0.12)" },
  { name: "θ", lo: 4, hi: 8, color: "rgba(122,158,122,0.12)" },
  { name: "α", lo: 8, hi: 13, color: "rgba(201,168,76,0.14)" },
  { name: "β", lo: 13, hi: 30, color: "rgba(192,122,90,0.12)" },
  { name: "γ", lo: 30, hi: 45, color: "rgba(160,112,176,0.12)" },
];

export class SpectrumRenderer {
  constructor(canvas, { channelCount = 4 } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.channelCount = channelCount;
    this.activeChannel = 0;
    this.fMax = 50;
    this._dpr = 1;
    this._resize();
    window.addEventListener("resize", () => this._resize());
  }

  _resize() {
    const parent = this.canvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    this._dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.floor(rect.width * this._dpr));
    this.canvas.height = Math.max(1, Math.floor(rect.height * this._dpr));
    this.canvas.style.width = rect.width + "px";
    this.canvas.style.height = rect.height + "px";
    this.ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    this.w = rect.width;
    this.h = rect.height;
  }

  setActiveChannel(ch) {
    this.activeChannel = Math.max(0, Math.min(ch, this.channelCount - 1));
  }

  draw(spectrum) {
    const ctx = this.ctx;
    const w = this.w, h = this.h;
    if (!w || !h || w < 2 || h < 2) return;

    ctx.fillStyle = "#0b0e14";
    ctx.fillRect(0, 0, w, h);

    const padL = 40, padR = 12, padT = 12, padB = 28;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    for (const b of BAND_REGIONS) {
      const x0 = padL + (b.lo / this.fMax) * plotW;
      const x1 = padL + (b.hi / this.fMax) * plotW;
      ctx.fillStyle = b.color;
      ctx.fillRect(x0, padT, x1 - x0, plotH);
    }

    ctx.strokeStyle = "#1e2533";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, padT);
    ctx.lineTo(padL, padT + plotH);
    ctx.lineTo(padL + plotW, padT + plotH);
    ctx.stroke();

    ctx.fillStyle = "#6b7a90";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    for (let f = 0; f <= this.fMax; f += 10) {
      const x = padL + (f / this.fMax) * plotW;
      ctx.beginPath();
      ctx.strokeStyle = "#151c28";
      ctx.moveTo(x, padT);
      ctx.lineTo(x, padT + plotH);
      ctx.stroke();
      ctx.fillText(String(f), x, padT + plotH + 14);
    }
    ctx.fillText("Hz", padL + plotW - 4, padT + plotH + 14);

    if (!spectrum || !spectrum.freqs || spectrum.freqs.length < 2) return;

    const { freqs, power } = spectrum;
    let maxP = 1e-12;
    for (let i = 0; i < freqs.length; i++) {
      if (freqs[i] > this.fMax) break;
      if (power[i] > maxP) maxP = power[i];
    }

    const color = CHANNEL_COLORS[this.activeChannel % CHANNEL_COLORS.length];
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < freqs.length; i++) {
      if (freqs[i] > this.fMax) break;
      const x = padL + (freqs[i] / this.fMax) * plotW;
      const y = padT + plotH - (power[i] / maxP) * plotH * 0.92;
      if (!started) { ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    let peakIdx = 0, peakP = -1;
    for (let i = 0; i < freqs.length; i++) {
      if (freqs[i] < 0.5 || freqs[i] > this.fMax) continue;
      if (power[i] > peakP) { peakP = power[i]; peakIdx = i; }
    }
    if (peakP > 0) {
      const px = padL + (freqs[peakIdx] / this.fMax) * plotW;
      const py = padT + plotH - (peakP / maxP) * plotH * 0.92;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#c8d0dc";
      ctx.textAlign = "left";
      ctx.fillText(`${freqs[peakIdx].toFixed(1)} Hz`, px + 6, py - 4);
    }
  }
}
