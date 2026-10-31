/**
 * Canvas 2D multi-channel oscilloscope renderer.
 * Reads from ChannelBuffer[] — never generates signal data itself.
 */
const CHANNEL_COLORS = [
  "#3d9cf0", "#3ecf8e", "#e0a84c", "#c77dff",
  "#f07178", "#56b6c2", "#d19a66", "#98c379",
];

export class WaveformRenderer {
  constructor(canvas, { channelCount = 4 } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.channelCount = channelCount;
    this.visible = new Array(channelCount).fill(true);
    this.gains = new Array(channelCount).fill(1);
    this.offsets = new Array(channelCount).fill(0);
    this.timebaseSec = 1;
    this.ampScale = 1;
    this.paused = false;
    this.frozen = false;
    this._freezeSnapshot = null;
    this.sampleRate = 250;
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

  setTimebase(sec) { this.timebaseSec = sec; }
  setAmpScale(s) { this.ampScale = s; }
  setSampleRate(sr) { this.sampleRate = sr; }
  setVisible(ch, v) { this.visible[ch] = v; }
  setGain(ch, g) { this.gains[ch] = g; }
  pause() { this.paused = true; }
  resume() { this.paused = false; this.frozen = false; this._freezeSnapshot = null; }

  freeze(buffers) {
    this.frozen = true;
    this._freezeSnapshot = buffers.map((b) => b.snapshot());
  }

  draw(buffers) {
    if (this.paused && !this.frozen) return;
    const ctx = this.ctx;
    const w = this.w, h = this.h;
    if (!w || !h || w < 2 || h < 2) return;

    ctx.fillStyle = "#0b0e14";
    ctx.fillRect(0, 0, w, h);

    const nCh = this.channelCount;
    const rowH = h / nCh;
    const samplesNeeded = Math.max(8, Math.floor(this.timebaseSec * this.sampleRate));

    ctx.strokeStyle = "#1a2230";
    ctx.lineWidth = 1;
    for (let c = 0; c <= nCh; c++) {
      const y = c * rowH;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    for (let i = 1; i < 10; i++) {
      const x = (i / 10) * w;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    ctx.strokeStyle = "#151c28";
    for (let c = 0; c < nCh; c++) {
      const mid = (c + 0.5) * rowH;
      ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(w, mid); ctx.stroke();
    }

    for (let c = 0; c < nCh; c++) {
      if (!this.visible[c]) continue;
      let samples;
      if (this.frozen && this._freezeSnapshot) samples = this._freezeSnapshot[c];
      else samples = buffers[c].latest(samplesNeeded);
      if (!samples || samples.length < 2) continue;

      const mid = (c + 0.5) * rowH;
      const scale = (rowH * 0.4) * this.gains[c] * this.ampScale;
      ctx.strokeStyle = CHANNEL_COLORS[c % CHANNEL_COLORS.length];
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      const len = samples.length;
      for (let i = 0; i < len; i++) {
        const x = (i / (len - 1)) * w;
        const y = mid - samples[i] * scale + this.offsets[c] * rowH * 0.1;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  getChannelColors() {
    return CHANNEL_COLORS.slice(0, this.channelCount);
  }
}
