/**
 * Browser / Node unit tests for eeg-loop web lab core.
 */
import { mulberry32 } from "../js/utils/rng.js";
import { psd, dominantFrequency, bandPowerFromPsd, nextPow2 } from "../js/utils/fft.js";
import { ChannelBuffer } from "../js/core/ChannelBuffer.js";
import { SyntheticEEGSource } from "../js/core/SyntheticEEGSource.js";
import { ArtifactDetector } from "../js/core/ArtifactDetector.js";
import { SignalAnalyzer } from "../js/core/SignalAnalyzer.js";
import { SessionRecorder, SessionPlayer } from "../js/session/SessionRecorder.js";
import { EEGPacketSource, parseSessionJsonl } from "../js/core/EEGPacketSource.js";

const results = [];
function assert(cond, msg) {
  results.push({ ok: !!cond, msg });
  if (!cond) console.error("FAIL:", msg);
  else console.log("ok:", msg);
}
function assertClose(a, b, eps, msg) {
  assert(Math.abs(a - b) < eps, `${msg} (${a} ≈ ${b})`);
}

{
  const a = mulberry32(42), b = mulberry32(42), c = mulberry32(99);
  const seqA = [a(), a(), a()], seqB = [b(), b(), b()], seqC = [c(), c(), c()];
  assert(seqA[0] === seqB[0] && seqA[1] === seqB[1], "same seed → same sequence");
  assert(seqA[0] !== seqC[0], "different seed → different sequence");
}
{
  const buf = new ChannelBuffer(8);
  for (let i = 0; i < 20; i++) buf.write(i);
  assert(buf.count === 8, "buffer capped at capacity");
  assert(buf.filled, "buffer reports filled");
  const snap = buf.snapshot();
  assert(snap.length === 8, "snapshot length");
  assert(snap[0] === 12 && snap[7] === 19, "circular rollover keeps newest");
  buf.clear();
  assert(buf.count === 0, "clear resets count");
}
{
  const s1 = new SyntheticEEGSource({ sampleRate: 250, channelCount: 2, seed: 7, alpha: 0.8 });
  const s2 = new SyntheticEEGSource({ sampleRate: 250, channelCount: 2, seed: 7, alpha: 0.8 });
  const s3 = new SyntheticEEGSource({ sampleRate: 250, channelCount: 2, seed: 8, alpha: 0.8 });
  const b1 = s1.generateBlock(64), b2 = s2.generateBlock(64), b3 = s3.generateBlock(64);
  let same = true, diff = false;
  for (let i = 0; i < 64; i++) {
    if (b1[i][0] !== b2[i][0]) same = false;
    if (b1[i][0] !== b3[i][0]) diff = true;
  }
  assert(same, "identical seeds → identical frames");
  assert(diff, "different seeds → different frames");
}
{
  const s = new SyntheticEEGSource({ sampleRate: 250, channelCount: 4, seed: 1 });
  const block = s.generateBlock(32);
  let differ = false;
  for (let i = 0; i < 32; i++) if (block[i][0] !== block[i][1]) differ = true;
  assert(differ, "channels are not identical (phase/jitter isolation)");
}
{
  const sr = 256, n = 512, freq = 10;
  const xs = new Float32Array(n);
  for (let i = 0; i < n; i++) xs[i] = Math.sin(2 * Math.PI * freq * i / sr);
  const { freqs, power } = psd(xs, sr);
  assertClose(dominantFrequency(freqs, power, 1, 40), 10, 1.5, "FFT identifies 10 Hz tone");
}
{
  const sr = 250, n = 512;
  const xs = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    xs[i] = 2 * Math.sin(2 * Math.PI * 10 * i / sr) + 0.3 * Math.sin(2 * Math.PI * 2 * i / sr);
  }
  const { freqs, power } = psd(xs, sr);
  assert(bandPowerFromPsd(freqs, power, 8, 13) > bandPowerFromPsd(freqs, power, 0.5, 4),
    "alpha band power > delta for alpha-dominant tone");
}
{
  const det = new ArtifactDetector();
  const flat = new Float32Array(128).fill(0);
  const spike = new Float32Array(128); spike[64] = 50;
  assert(det.detect(flat).probability > 0.3, "flatline raises artifact score");
  assert(det.detect(spike).probability > 0.3, "spike raises artifact score");
}
{
  const an = new SignalAnalyzer({ sampleRate: 250, windowSize: 128 });
  assert(an.analyze(new Float32Array(4)).inferenceState === "NO_VALID_INFERENCE",
    "short input → invalid inference");
}
{
  const rec = new SessionRecorder({ sampleRate: 250, channelCount: 2 });
  rec.start({ seed: 42 });
  const src = new SyntheticEEGSource({ sampleRate: 250, channelCount: 2, seed: 42 });
  const frames = src.generateBlock(50);
  for (let i = 0; i < frames.length; i++) rec.pushFrame(frames[i], i * 4000);
  const exp = rec.stop();
  assert(exp.meta.sampleCount === 50, "recorded sample count");
  assert(exp.rawJsonl.includes("eeg-loop.session"), "export has session header");
  assert(exp.rawJsonl.includes('"simulated":true'), "marked simulated");
  const player = new SessionPlayer();
  player.load(exp.rawJsonl);
  let replayed = 0, match = true;
  for (const { frame } of player.frames()) {
    if (frame[0] !== frames[replayed][0]) match = false;
    replayed++;
  }
  assert(replayed === 50, "replay frame count");
  assert(match, "replay matches original raw samples");
}
{
  assert(nextPow2(300) === 512, "nextPow2(300)=512");
  assert(nextPow2(512) === 512, "nextPow2(512)=512");
}

{
  const header = {
    format: "eeg-loop.session", version: 2, session_id: "t1",
    sample_rate: 250, channel_count: 2, channel_names: ["ch0","ch1"],
    source: "synthetic", created_at: "2026-01-01T00:00:00Z",
  };
  const pkt0 = {
    sequence: 0, timestamp_us: 0, sample_rate: 250, channel_count: 2,
    samples: [[1, 2], [3, 4], [5, 6]], status: 0, quality: 1,
  };
  const pkt1 = {
    sequence: 1, timestamp_us: 12000, sample_rate: 250, channel_count: 2,
    samples: [[7, 8]], status: 0, quality: 1,
  };
  const fin = { record_type: "finalization", session_id: "t1", status: "finalized" };
  const jsonl = [header, pkt0, pkt1, fin].map((o) => JSON.stringify(o)).join("\n") + "\n";
  const parsed = parseSessionJsonl(jsonl);
  assert(parsed.packets.length === 2, "parseSessionJsonl skips finalization");
  assert(parsed.header.session_id === "t1", "parseSessionJsonl header");
  assert(parsed.diagnostics.length === 0, "clean session has no diagnostics");
  const src = new EEGPacketSource({ rawJsonl: jsonl });
  assert(src.frameCount === 4, "EEGPacketSource expands packet rows to frames");
  const collected = [];
  for (const f of src.frames()) collected.push(Array.from(f.frame));
  assert(collected.length === 4 && collected[0][0] === 1 && collected[3][0] === 7,
    "EEGPacketSource frame order matches packet samples");
  const gapPkt = { ...pkt1, sequence: 5 };
  const gapJsonl = [header, pkt0, gapPkt].map((o) => JSON.stringify(o)).join("\n");
  const gapParsed = parseSessionJsonl(gapJsonl);
  assert(gapParsed.diagnostics.some((d) => d.includes("gap")), "sequence gap is diagnosed, not repaired");
}

const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${passed} passed, ${failed} failed out of ${results.length}`);
if (typeof window !== "undefined") window.__EEG_TEST_RESULTS__ = { passed, failed, results };
export { results, passed, failed };
