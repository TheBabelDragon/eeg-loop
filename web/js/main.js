/**
 * eeg-loop Browser EEG Laboratory — main entry.
 * All signals are SIMULATED. Offline-capable. No medical claims.
 */
import { SyntheticEEGSource } from "./core/SyntheticEEGSource.js";
import { ChannelBuffer } from "./core/ChannelBuffer.js";
import { SignalAnalyzer } from "./core/SignalAnalyzer.js";
import { WaveformRenderer } from "./render/WaveformRenderer.js";
import { SpectrumRenderer } from "./render/SpectrumRenderer.js";
import { SessionRecorder, SessionPlayer } from "./session/SessionRecorder.js";
import { EEGPacketSource } from "./core/EEGPacketSource.js";

const CHANNEL_COUNT = 4;
const BUFFER_CAP = 8192;

let source = null;
let buffers = [];
let analyzer = null;
let waveRenderer = null;
let spectrumRenderer = null;
let recorder = null;
let lastExport = null;
let analysisChannel = 0;
let currentView = "waveform";
let analysisTimer = null;

function init() {
  const waveCanvas = document.getElementById("waveform-canvas");
  const specCanvas = document.getElementById("spectrum-canvas");
  for (let i = 0; i < CHANNEL_COUNT; i++) buffers.push(new ChannelBuffer(BUFFER_CAP));
  analyzer = new SignalAnalyzer({ sampleRate: 250, windowSize: 512 });
  waveRenderer = new WaveformRenderer(waveCanvas, { channelCount: CHANNEL_COUNT });
  spectrumRenderer = new SpectrumRenderer(specCanvas, { channelCount: CHANNEL_COUNT });
  recorder = new SessionRecorder({ sampleRate: 250, channelCount: CHANNEL_COUNT });
  buildChannelToggles();
  bindControls();
  bindTabs();
  applyPreset("clean-alpha");

  function frame() {
    if (currentView === "waveform") waveRenderer.draw(buffers);
    else {
      const snap = buffers[analysisChannel].latest(512);
      spectrumRenderer.draw(analyzer.analyze(snap));
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  analysisTimer = setInterval(updateAnalysisPanel, 200);
  console.info("[eeg-lab] Browser EEG Laboratory ready — all signals SIMULATED");
}

function createSource() {
  const seed = parseInt(document.getElementById("seed").value, 10) || 42;
  const sampleRate = parseFloat(document.getElementById("sample-rate").value) || 250;
  if (source) source.stop();
  source = new SyntheticEEGSource({
    sampleRate, channelCount: CHANNEL_COUNT, seed,
    masterAmp: parseFloat(document.getElementById("master-amp").value),
    noise: parseFloat(document.getElementById("noise").value),
    lineFreq: parseFloat(document.getElementById("line-freq").value),
    delta: +document.getElementById("band-delta").value,
    theta: +document.getElementById("band-theta").value,
    alpha: +document.getElementById("band-alpha").value,
    beta:  +document.getElementById("band-beta").value,
    gamma: +document.getElementById("band-gamma").value,
    onFrame(frame, timestampUs) {
      for (let c = 0; c < CHANNEL_COUNT; c++) buffers[c].write(frame[c]);
      if (recorder.recording) recorder.pushFrame(frame, timestampUs);
    },
  });
  analyzer.setSampleRate(sampleRate);
  waveRenderer.setSampleRate(sampleRate);
  recorder.sampleRate = sampleRate;
  return source;
}

function startGenerator() {
  createSource();
  source.start();
  setGenState("running");
  document.getElementById("btn-start").disabled = true;
  document.getElementById("btn-stop").disabled = false;
}
function stopGenerator() {
  if (source) source.stop();
  setGenState("stopped");
  document.getElementById("btn-start").disabled = false;
  document.getElementById("btn-stop").disabled = true;
}
function setGenState(s) {
  const el = document.getElementById("gen-state");
  el.textContent = s.toUpperCase();
  el.className = "state " + s;
}

function bindControls() {
  document.getElementById("btn-start").addEventListener("click", startGenerator);
  document.getElementById("btn-stop").addEventListener("click", stopGenerator);
  document.getElementById("btn-pause").addEventListener("click", () => {
    waveRenderer.pause();
    document.getElementById("btn-pause").disabled = true;
    document.getElementById("btn-resume").disabled = false;
    setGenState(source?.running ? "paused" : "stopped");
  });
  document.getElementById("btn-resume").addEventListener("click", () => {
    waveRenderer.resume();
    document.getElementById("btn-pause").disabled = false;
    document.getElementById("btn-resume").disabled = true;
    setGenState(source?.running ? "running" : "stopped");
  });
  document.getElementById("btn-reset").addEventListener("click", () => buffers.forEach((b) => b.clear()));
  document.getElementById("btn-freeze").addEventListener("click", () => waveRenderer.freeze(buffers));
  document.getElementById("timebase").addEventListener("change", (e) => waveRenderer.setTimebase(parseFloat(e.target.value)));
  document.getElementById("amp-scale").addEventListener("input", (e) => {
    const v = parseFloat(e.target.value);
    waveRenderer.setAmpScale(v);
    document.getElementById("amp-scale-val").textContent = v.toFixed(1) + "×";
  });

  const bindRange = (id, fn) => {
    document.getElementById(id).addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      fn(v);
      const span = e.target.parentElement.querySelector("span");
      if (span) span.textContent = v.toFixed(2);
    });
  };
  bindRange("master-amp", (v) => { if (source) source.setMasterAmp(v); document.getElementById("master-amp-val").textContent = v.toFixed(2); });
  bindRange("noise", (v) => { if (source) source.setNoise(v); document.getElementById("noise-val").textContent = v.toFixed(2); });
  for (const band of ["delta", "theta", "alpha", "beta", "gamma"]) {
    document.getElementById(`band-${band}`).addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      e.target.parentElement.querySelector("span").textContent = v.toFixed(2);
      if (source) source.setBandAmps({ [band]: v });
    });
  }
  document.getElementById("line-freq").addEventListener("change", (e) => {
    if (source) source.setLineFreq(parseFloat(e.target.value));
  });

  document.getElementById("art-blink").addEventListener("click", () => source?.injectBlink(0));
  document.getElementById("art-muscle").addEventListener("click", () => source?.injectMuscle());
  document.getElementById("art-disconnect").addEventListener("click", () => {
    if (!source) return;
    if (source.artifacts?.disconnect?.active) source.clearDisconnect();
    else source.injectDisconnect?.(0);
  });
  document.getElementById("art-line").addEventListener("click", () => {
    if (!source || typeof source.setLineAmp !== "function") return;
    source.setLineAmp(source.lineAmp > 0 ? 0 : 0.4);
  });
  document.getElementById("art-spike").addEventListener("click", () => source?.injectSpike?.(0));
  document.getElementById("preset").addEventListener("change", (e) => { if (e.target.value) applyPreset(e.target.value); });

  document.getElementById("btn-rec-start").addEventListener("click", () => {
    const seed = parseInt(document.getElementById("seed").value, 10) || 42;
    recorder.sampleRate = source?.sampleRate || 250;
    recorder.start({ seed, source: "synthetic-browser" });
    document.getElementById("btn-rec-start").disabled = true;
    document.getElementById("btn-rec-stop").disabled = false;
    document.getElementById("btn-rec-start").classList.add("recording");
    document.getElementById("rec-status").textContent = "Recording…";
  });
  document.getElementById("btn-rec-stop").addEventListener("click", () => {
    lastExport = recorder.stop();
    document.getElementById("btn-rec-start").disabled = false;
    document.getElementById("btn-rec-stop").disabled = true;
    document.getElementById("btn-rec-start").classList.remove("recording");
    document.getElementById("rec-status").textContent =
      lastExport ? `Recorded ${lastExport.meta.sampleCount} samples` : "Idle";
  });
  document.getElementById("btn-export").addEventListener("click", exportSession);
  document.getElementById("btn-replay").addEventListener("click", replaySession);
  document.getElementById("session-file").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const text = await file.text();
    loadSessionFile(text, file.name);
    e.target.value = "";
  });
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      tab.classList.add("active");
      currentView = tab.dataset.view;
      document.getElementById(`${currentView}-view`).classList.add("active");
      requestAnimationFrame(() => { waveRenderer._resize(); spectrumRenderer._resize(); });
    });
  });
}

function buildChannelToggles() {
  const root = document.getElementById("channel-toggles");
  const labels = document.getElementById("channel-labels");
  const colors = waveRenderer.getChannelColors();
  root.innerHTML = "";
  labels.innerHTML = "";
  for (let c = 0; c < CHANNEL_COUNT; c++) {
    const lab = document.createElement("label");
    lab.innerHTML = `<input type="checkbox" checked data-ch="${c}" />
      <span class="ch-dot" style="background:${colors[c]}"></span> CH${c}`;
    lab.querySelector("input").addEventListener("change", (e) => waveRenderer.setVisible(c, e.target.checked));
    root.appendChild(lab);
    const tag = document.createElement("span");
    tag.style.color = colors[c];
    tag.textContent = `CH${c}`;
    labels.appendChild(tag);
  }
}

const PRESETS = {
  "clean-alpha": { delta: 0.15, theta: 0.2, alpha: 0.85, beta: 0.2, gamma: 0.08, noise: 0.05, master: 1 },
  "mixed":       { delta: 0.35, theta: 0.4, alpha: 0.45, beta: 0.35, gamma: 0.15, noise: 0.1, master: 1 },
  "slow-wave":   { delta: 0.9,  theta: 0.55, alpha: 0.15, beta: 0.1, gamma: 0.05, noise: 0.06, master: 1 },
  "hf-noise":    { delta: 0.1,  theta: 0.15, alpha: 0.2, beta: 0.6, gamma: 0.7, noise: 0.25, master: 1 },
  "blink":       { delta: 0.2,  theta: 0.25, alpha: 0.6, beta: 0.25, gamma: 0.1, noise: 0.08, master: 1, blink: true },
  "disconnect":  { delta: 0.1,  theta: 0.1, alpha: 0.1, beta: 0.1, gamma: 0.05, noise: 0.02, master: 0.3, disconnect: true },
  "noisy":       { delta: 0.3,  theta: 0.3, alpha: 0.3, beta: 0.4, gamma: 0.3, noise: 0.45, master: 1, line: true },
};

function applyPreset(name) {
  const p = PRESETS[name];
  if (!p) return;
  const setBand = (b, v) => {
    const el = document.getElementById(`band-${b}`);
    el.value = v;
    el.parentElement.querySelector("span").textContent = v.toFixed(2);
  };
  setBand("delta", p.delta); setBand("theta", p.theta); setBand("alpha", p.alpha);
  setBand("beta", p.beta); setBand("gamma", p.gamma);
  document.getElementById("noise").value = p.noise;
  document.getElementById("noise-val").textContent = p.noise.toFixed(2);
  document.getElementById("master-amp").value = p.master;
  document.getElementById("master-amp-val").textContent = p.master.toFixed(2);
  if (source && typeof source.setBandAmps === "function") {
    source.setBandAmps({ delta: p.delta, theta: p.theta, alpha: p.alpha, beta: p.beta, gamma: p.gamma });
    source.setNoise(p.noise);
    source.setMasterAmp(p.master);
    source.clearDisconnect?.();
    source.setLineAmp?.(0);
    if (p.blink) source.injectBlink?.(0);
    if (p.disconnect) source.injectDisconnect?.(0);
    if (p.line) source.setLineAmp?.(0.4);
  }
}

function updateAnalysisPanel() {
  const snap = buffers[analysisChannel].latest(512);
  const r = analyzer.analyze(snap);
  if (recorder.recording) recorder.logAnalysis(r);
  const fmt = (v, d = 3) => (Number.isFinite(v) ? v.toFixed(d) : "—");
  document.getElementById("a-rms").textContent = fmt(r.rms);
  document.getElementById("a-pp").textContent = fmt(r.peakToPeak);
  document.getElementById("a-mean").textContent = fmt(r.mean);
  document.getElementById("a-var").textContent = fmt(r.variance, 4);
  document.getElementById("a-dom").textContent = fmt(r.dominantFrequency, 1) + " Hz";
  document.getElementById("a-art").textContent = fmt(r.artifactProbability, 2);
  document.getElementById("a-delta").textContent = `δ ${fmt(r.relativePowers.delta, 2)}`;
  document.getElementById("a-theta").textContent = `θ ${fmt(r.relativePowers.theta, 2)}`;
  document.getElementById("a-alpha").textContent = `α ${fmt(r.relativePowers.alpha, 2)}`;
  document.getElementById("a-beta").textContent  = `β ${fmt(r.relativePowers.beta, 2)}`;
  document.getElementById("a-gamma").textContent = `γ ${fmt(r.relativePowers.gamma, 2)}`;
  document.getElementById("a-qual").textContent = fmt(r.quality, 2);
  const inf = document.getElementById("inference-state");
  inf.textContent = r.inferenceState;
  inf.className = "inference-state " +
    (r.inferenceState === "NO_VALID_INFERENCE" ? "invalid" :
     r.inferenceState === "VALID" ? "valid" : "");
  const sr = source?.sampleRate || 250;
  document.getElementById("sample-rate-display").textContent = sr + " Hz";
  document.getElementById("elapsed-display").textContent =
    (source ? source.sampleIndex / sr : 0).toFixed(2) + " s";
  document.getElementById("buffer-display").textContent =
    `buf ${buffers[0].count}/${buffers[0].capacity}`;
}

function exportSession() {
  if (!lastExport) {
    const seed = parseInt(document.getElementById("seed").value, 10) || 42;
    recorder.start({ seed });
    const n = buffers[0].count;
    const snaps = buffers.map((b) => b.snapshot());
    for (let i = 0; i < n; i++) {
      const frame = new Float32Array(CHANNEL_COUNT);
      for (let c = 0; c < CHANNEL_COUNT; c++) frame[c] = snaps[c][i];
      recorder.pushFrame(frame, Math.round((i / (source?.sampleRate || 250)) * 1e6));
    }
    lastExport = recorder.stop();
  }
  if (!lastExport) return;
  const blob = new Blob([lastExport.rawJsonl], { type: "application/x-ndjson" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${lastExport.meta.sessionId}.eeg.jsonl`;
  a.click();
  URL.revokeObjectURL(a.href);
  const dBlob = new Blob([JSON.stringify(lastExport.derived, null, 2)], { type: "application/json" });
  const a2 = document.createElement("a");
  a2.href = URL.createObjectURL(dBlob);
  a2.download = `${lastExport.meta.sessionId}.derived.json`;
  a2.click();
  URL.revokeObjectURL(a2.href);
  document.getElementById("rec-status").textContent = `Exported ${lastExport.meta.sampleCount} samples`;
}

function replaySession() {
  if (!lastExport) {
    document.getElementById("rec-status").textContent = "Nothing to replay — record first";
    return;
  }
  stopGenerator();
  buffers.forEach((b) => b.clear());
  const player = new SessionPlayer();
  player.load(lastExport.rawJsonl);
  let count = 0;
  for (const { frame } of player.frames()) {
    for (let c = 0; c < Math.min(CHANNEL_COUNT, frame.length); c++) buffers[c].write(frame[c]);
    count++;
  }
  document.getElementById("rec-status").textContent = `Replayed ${count} samples`;
  waveRenderer.resume();
}

function loadSessionFile(rawJsonl, name = "session") {
  try {
    stopGenerator();
    buffers.forEach((b) => b.clear());
    const pktSource = new EEGPacketSource({
      rawJsonl,
      onFrame(frame) {
        const n = Math.min(CHANNEL_COUNT, frame.length);
        for (let c = 0; c < n; c++) buffers[c].write(frame[c]);
      },
    });
    if (pktSource.diagnostics.length) {
      console.warn("[eeg-lab] session diagnostics:", pktSource.diagnostics);
    }
    source = pktSource;
    analyzer.setSampleRate(pktSource.sampleRate);
    waveRenderer.setSampleRate(pktSource.sampleRate);
    pktSource.start();
    setGenState("running");
    document.getElementById("btn-start").disabled = true;
    document.getElementById("btn-stop").disabled = false;
    const sim = pktSource.simulated ? "SIMULATED" : "recorded";
    document.getElementById("rec-status").textContent =
      `Playing ${name} (${pktSource.frameCount} frames, ${sim})`;
    if (pktSource.diagnostics.length) {
      document.getElementById("rec-status").textContent +=
        ` · ${pktSource.diagnostics.length} diagnostic(s)`;
    }
  } catch (err) {
    console.error(err);
    document.getElementById("rec-status").textContent = `Load failed: ${err.message}`;
  }
}

init();
