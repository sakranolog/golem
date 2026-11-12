// Sound engine for The Too-Literal Golem. Web Audio only, no libraries.
// Plays generated files from /audio/manifest.json when present and falls back to
// procedural synthesis for any id without a file, so the game always sounds good.

const BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.BASE_URL) || '/';
const STORE_KEY = 'golem.audio';
const rnd = (a = 0, b = 1) => a + Math.random() * (b - a);
const pick = arr => arr[Math.floor(Math.random() * arr.length)];

// ---------------------------------------------------------------------------
// Synthesis helpers
// ---------------------------------------------------------------------------
let _noise = null;
function noiseBuffer(c) {
  if (_noise && _noise.sampleRate === c.sampleRate) return _noise;
  const len = c.sampleRate * 2;
  const b = c.createBuffer(1, len, c.sampleRate);
  const d = b.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  return (_noise = b);
}

function envGain(c, t, a, d, peak) {
  const g = c.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(Math.max(peak, 0.0002), t + a);
  g.gain.exponentialRampToValueAtTime(0.0001, t + a + d);
  return g;
}

function noiseBurst(c, out, t, { dur = 0.1, gain = 0.5, type = 'lowpass', f = 800, f2 = null, q = 1, a = 0.002 } = {}) {
  const s = c.createBufferSource();
  s.buffer = noiseBuffer(c);
  s.loop = true;
  const flt = c.createBiquadFilter();
  flt.type = type;
  flt.frequency.setValueAtTime(f, t);
  if (f2) flt.frequency.exponentialRampToValueAtTime(f2, t + a + dur);
  flt.Q.value = q;
  const g = envGain(c, t, a, dur, gain);
  s.connect(flt).connect(g).connect(out);
  s.start(t, Math.random());
  s.stop(t + a + dur + 0.05);
}

function tone(c, out, t, { type = 'sine', f = 440, f2 = null, dur = 0.3, gain = 0.3, a = 0.005, lp = 0 } = {}) {
  const o = c.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(f, t);
  if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + a + dur);
  const g = envGain(c, t, a, dur, gain);
  let n = o;
  if (lp) {
    const flt = c.createBiquadFilter();
    flt.type = 'lowpass';
    flt.frequency.value = lp;
    o.connect(flt);
    n = flt;
  }
  n.connect(g).connect(out);
  o.start(t);
  o.stop(t + a + dur + 0.05);
}

// FM bell: carrier + inharmonic modulator with decaying index.
function bell(c, out, t, f, dur = 1, gain = 0.25, ratio = 2.76, idx = 2.5) {
  const car = c.createOscillator();
  const mod = c.createOscillator();
  const mg = c.createGain();
  car.frequency.value = f;
  mod.frequency.value = f * ratio;
  mg.gain.setValueAtTime(f * idx, t);
  mg.gain.exponentialRampToValueAtTime(f * 0.01, t + dur);
  mod.connect(mg).connect(car.frequency);
  const g = envGain(c, t, 0.003, dur, gain);
  car.connect(g).connect(out);
  car.start(t); mod.start(t);
  car.stop(t + dur + 0.05); mod.stop(t + dur + 0.05);
}

const midi = n => 440 * Math.pow(2, (n - 69) / 12);

// ---------------------------------------------------------------------------
// Procedural one-shots: (ctx, out, t, P) => duration. P = pitch factor.
// ---------------------------------------------------------------------------
const SYNTH = {};
[1, 2, 3].forEach(i => {
  SYNTH[`step_${i}`] = (c, o, t, P) => {
    const k = 1 + (i - 2) * 0.1;
    tone(c, o, t, { f: 95 * k * P, f2: 42 * P, dur: 0.22, gain: 0.9 });
    noiseBurst(c, o, t, { dur: 0.12, gain: 0.55, f: 420 * k * P });
    for (let n = 0; n < 4; n++) noiseBurst(c, o, t + rnd(0.04, 0.3), { dur: 0.025, gain: rnd(0.05, 0.14), type: 'highpass', f: rnd(2200, 3600), q: 2 });
    return 0.5;
  };
  SYNTH[`golem_grunt_${i}`] = (c, o, t, P) => {
    const f = (62 + i * 9) * P;
    tone(c, o, t, { type: 'sawtooth', f: f * 1.15, f2: f * 0.8, dur: 0.45, gain: 0.5, a: 0.04, lp: 380 });
    tone(c, o, t, { type: 'square', f: f * 0.5, f2: f * 0.4, dur: 0.4, gain: 0.2, a: 0.04, lp: 200 });
    noiseBurst(c, o, t, { dur: 0.4, gain: 0.18, f: 260, q: 2, a: 0.05 });
    return 0.6;
  };
});
SYNTH.turn = (c, o, t, P) => {
  noiseBurst(c, o, t, { dur: 0.45, gain: 0.4, type: 'bandpass', f: 280 * P, f2: 620 * P, q: 6, a: 0.05 });
  tone(c, o, t, { type: 'sawtooth', f: 62 * P, f2: 88 * P, dur: 0.45, gain: 0.1, lp: 300 });
  return 0.6;
};
SYNTH.bonk = (c, o, t, P) => {
  tone(c, o, t, { f: 150 * P, f2: 48 * P, dur: 0.32, gain: 1 });
  tone(c, o, t, { type: 'triangle', f: 230 * P, f2: 110 * P, dur: 0.2, gain: 0.35 });
  noiseBurst(c, o, t, { dur: 0.08, gain: 0.5, f: 700 });
  return 0.5;
};
SYNTH.bonk_books = (c, o, t, P) => {
  SYNTH.bonk(c, o, t, P);
  [0.16, 0.3, 0.41, 0.55, 0.66].forEach(d => {
    noiseBurst(c, o, t + d, { dur: 0.07, gain: rnd(0.3, 0.5), f: rnd(700, 1200) });
    tone(c, o, t + d, { f: rnd(120, 190) * P, f2: 70, dur: 0.1, gain: 0.3 });
  });
  return 1;
};
SYNTH.pickup = (c, o, t, P) => {
  noiseBurst(c, o, t, { dur: 0.22, gain: 0.25, type: 'bandpass', f: 1200 * P, f2: 2500 * P, q: 2, a: 0.03 });
  tone(c, o, t, { f: 300 * P, f2: 460 * P, dur: 0.1, gain: 0.12 });
  return 0.35;
};
SYNTH.putdown = (c, o, t, P) => {
  tone(c, o, t, { f: 125 * P, f2: 68 * P, dur: 0.2, gain: 0.7 });
  noiseBurst(c, o, t, { dur: 0.06, gain: 0.35, f: 800 });
  return 0.3;
};
SYNTH.jug_smash = (c, o, t, P) => {
  tone(c, o, t, { f: 110 * P, f2: 50, dur: 0.2, gain: 0.6 });
  noiseBurst(c, o, t, { dur: 0.35, gain: 0.55, type: 'highpass', f: 1500 * P, q: 0.7 });
  for (let n = 0; n < 12; n++) tone(c, o, t + rnd(0.02, 0.7), { f: rnd(1800, 5200) * P, dur: 0.05, gain: rnd(0.04, 0.12), type: 'triangle' });
  return 1;
};
SYNTH.awaken = (c, o, t, P) => {
  tone(c, o, t, { type: 'sawtooth', f: 70 * P, f2: 180 * P, dur: 0.9, gain: 0.25, a: 0.7, lp: 500 });
  tone(c, o, t, { f: 90 * P, f2: 200 * P, dur: 0.9, gain: 0.3, a: 0.7 });
  [880, 1318, 1760, 2637].forEach((f, i) => bell(c, o, t + 0.95 + i * 0.07, f * P, 1.0, 0.16));
  return 2;
};
SYNTH.sleep = (c, o, t, P) => {
  tone(c, o, t, { f: 200 * P, f2: 55 * P, dur: 0.9, gain: 0.3, a: 0.03 });
  tone(c, o, t, { type: 'sawtooth', f: 100 * P, f2: 40 * P, dur: 0.9, gain: 0.1, lp: 300 });
  return 1.1;
};
SYNTH.stone_place = (c, o, t, P) => {
  noiseBurst(c, o, t, { dur: 0.025, gain: 0.5, type: 'highpass', f: 2000 });
  tone(c, o, t, { f: 950 * P, f2: 620 * P, dur: 0.06, gain: 0.3 });
  tone(c, o, t, { f: 190 * P, f2: 120 * P, dur: 0.12, gain: 0.5 });
  return 0.25;
};
SYNTH.stone_remove = (c, o, t, P) => {
  noiseBurst(c, o, t, { dur: 0.3, gain: 0.25, type: 'bandpass', f: 900 * P, f2: 400 * P, q: 3, a: 0.03 });
  return 0.4;
};
SYNTH.ui_tap = (c, o, t, P) => {
  tone(c, o, t, { f: 720 * P, f2: 410 * P, dur: 0.06, gain: 0.4 });
  noiseBurst(c, o, t, { dur: 0.02, gain: 0.25, type: 'bandpass', f: 1500, q: 2 });
  return 0.15;
};
SYNTH.fall = (c, o, t, P) => {
  tone(c, o, t, { type: 'triangle', f: 1200 * P, f2: 140 * P, dur: 1.4, gain: 0.22 });
  noiseBurst(c, o, t, { dur: 1.4, gain: 0.2, type: 'bandpass', f: 2000, f2: 300, q: 1.5, a: 0.05 });
  tone(c, o, t + 1.9, { f: 80, f2: 38, dur: 0.35, gain: 0.5 });
  noiseBurst(c, o, t + 1.9, { dur: 0.15, gain: 0.25, f: 300 });
  return 2.5;
};
SYNTH.cat_meow = (c, o, t, P) => {
  const osc = c.createOscillator();
  osc.type = 'sawtooth';
  osc.frequency.setValueAtTime(480 * P, t);
  osc.frequency.linearRampToValueAtTime(760 * P, t + 0.25);
  osc.frequency.linearRampToValueAtTime(430 * P, t + 0.75);
  const bp = c.createBiquadFilter();
  bp.type = 'bandpass'; bp.Q.value = 4;
  bp.frequency.setValueAtTime(900, t);
  bp.frequency.linearRampToValueAtTime(1900, t + 0.3);
  bp.frequency.linearRampToValueAtTime(1000, t + 0.75);
  const g = envGain(c, t, 0.06, 0.7, 0.45);
  osc.connect(bp).connect(g).connect(o);
  osc.start(t); osc.stop(t + 0.85);
  return 0.85;
};
SYNTH.cat_purr = (c, o, t, P) => {
  const s = c.createBufferSource();
  s.buffer = noiseBuffer(c); s.loop = true;
  const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 320;
  const g = c.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(0.22, t + 0.15);
  g.gain.setValueAtTime(0.22, t + 1.0);
  g.gain.linearRampToValueAtTime(0.0001, t + 1.4);
  const lfo = c.createOscillator(); lfo.frequency.value = 25 * P;
  const lg = c.createGain(); lg.gain.value = 0.15;
  lfo.connect(lg).connect(g.gain);
  s.connect(lp).connect(g).connect(o);
  s.start(t); lfo.start(t); s.stop(t + 1.45); lfo.stop(t + 1.45);
  return 1.5;
};
SYNTH.plant_bloom = (c, o, t, P) => {
  [0, 2, 4, 7, 9, 12, 16].forEach((n, i) => bell(c, o, t + i * 0.12, midi(72 + n) * P, 0.9, 0.14));
  noiseBurst(c, o, t, { dur: 1.2, gain: 0.08, type: 'highpass', f: 4000, a: 0.8 });
  return 2;
};
SYNTH.letter_collect = (c, o, t, P) => {
  bell(c, o, t, 880 * P, 0.6, 0.25);
  bell(c, o, t + 0.1, 1318 * P, 0.8, 0.25);
  return 1;
};
SYNTH.candle_light = (c, o, t, P) => {
  noiseBurst(c, o, t, { dur: 0.12, gain: 0.3, type: 'bandpass', f: 3000, q: 1 });
  noiseBurst(c, o, t + 0.15, { dur: 0.35, gain: 0.3, f: 500 * P, f2: 1600 * P, a: 0.06 });
  return 0.7;
};
SYNTH.sweep = (c, o, t, P) => {
  [0, 0.5].forEach(d => noiseBurst(c, o, t + d, { dur: 0.4, gain: 0.25, type: 'bandpass', f: 1800 * P, f2: 1000 * P, q: 0.7, a: 0.12 }));
  return 1;
};
SYNTH.star = (c, o, t, P) => {
  bell(c, o, t, 1760 * P, 1.1, 0.25, 3.5, 1.5);
  bell(c, o, t, 2349 * P, 0.6, 0.08);
  return 1.2;
};
SYNTH.golem_huh = (c, o, t, P) => {
  tone(c, o, t, { type: 'sawtooth', f: 66 * P, f2: 100 * P, dur: 0.65, gain: 0.45, a: 0.08, lp: 380 });
  noiseBurst(c, o, t, { dur: 0.6, gain: 0.12, f: 260, q: 2, a: 0.1 });
  return 0.8;
};
SYNTH.golem_happy = (c, o, t, P) => {
  [0, 0.19, 0.38].forEach((d, i) => tone(c, o, t + d, { type: 'sawtooth', f: (84 + i * 6) * P, f2: 70 * P, dur: 0.14, gain: 0.45, a: 0.02, lp: 420 }));
  return 0.7;
};
SYNTH.golem_oops = (c, o, t, P) => {
  tone(c, o, t, { type: 'sawtooth', f: 96 * P, f2: 80 * P, dur: 0.2, gain: 0.42, a: 0.03, lp: 380 });
  tone(c, o, t + 0.28, { type: 'sawtooth', f: 78 * P, f2: 52 * P, dur: 0.4, gain: 0.42, a: 0.03, lp: 340 });
  return 0.8;
};
SYNTH.whoosh_ui = (c, o, t, P) => {
  noiseBurst(c, o, t, { dur: 0.3, gain: 0.2, type: 'bandpass', f: 400 * P, f2: 2500 * P, q: 0.8, a: 0.1 });
  return 0.45;
};
SYNTH.sting_success = (c, o, t, P) => {
  [62, 66, 69, 74, 78, 81, 86].forEach((n, i) => {
    tone(c, o, t + i * 0.09, { type: 'triangle', f: midi(n) * P, dur: 0.5, gain: 0.3 });
    bell(c, o, t + i * 0.09, midi(n + 12) * P, 0.6, 0.07);
  });
  [62, 66, 69, 74].forEach(n => tone(c, o, t + 0.7, { type: 'triangle', f: midi(n) * P, dur: 1.8, gain: 0.2, a: 0.02 }));
  bell(c, o, t + 0.7, midi(86) * P, 2, 0.15);
  return 3;
};
SYNTH.sting_fail = (c, o, t, P) => {
  [[392, 0.38], [370, 0.38], [349, 0.38], [294, 1.2]].reduce((tt, [f, d], i) => {
    const osc = c.createOscillator();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(f * P, tt);
    osc.frequency.linearRampToValueAtTime(f * P * (i === 3 ? 0.85 : 0.96), tt + d);
    const lp = c.createBiquadFilter();
    lp.type = 'lowpass'; lp.Q.value = 5;
    lp.frequency.setValueAtTime(350, tt);
    lp.frequency.linearRampToValueAtTime(1100, tt + d * 0.4);
    lp.frequency.linearRampToValueAtTime(400, tt + d);
    const g = envGain(c, tt, 0.04, d, 0.3);
    osc.connect(lp).connect(g).connect(o);
    osc.start(tt); osc.stop(tt + d + 0.1);
    return tt + (i < 3 ? 0.42 : 0);
  }, t);
  return 2.4;
};
SYNTH.sting_final = (c, o, t, P) => {
  [50, 57, 62, 66].forEach(n => tone(c, o, t, { type: 'sawtooth', f: midi(n) * P, dur: 5.5, gain: 0.07, a: 2.5, lp: 900 }));
  [62, 66, 69, 74, 78, 81, 86, 90, 93].forEach((n, i) => {
    bell(c, o, t + 1 + i * 0.22, midi(n) * P, 1.4, 0.13);
    tone(c, o, t + 1 + i * 0.22, { type: 'triangle', f: midi(n - 12) * P, dur: 0.5, gain: 0.15 });
  });
  [62, 66, 69, 74, 86].forEach(n => tone(c, o, t + 3.4, { type: 'triangle', f: midi(n) * P, dur: 3.5, gain: 0.16, a: 0.05 }));
  bell(c, o, t + 3.4, midi(98) * P, 3, 0.15);
  return 7;
};

// ---------------------------------------------------------------------------
// Procedural looping beds: (ctx, out, kind) => { stop() }
// ---------------------------------------------------------------------------
function makeMusic(c, out, kind) {
  const think = kind === 'music_think';
  const bpm = think ? 60 : 94;
  const step = 60 / bpm / 2;
  const SC = [0, 1, 4, 5, 7, 8, 10]; // D freygish
  const noteAt = (deg, oct) => 50 + SC[((deg % 7) + 7) % 7] + 12 * (oct + Math.floor(deg / 7));
  const prog = [0, 3, 1, 0];
  const bus = c.createGain();
  bus.gain.value = think ? 0.7 : 1;
  bus.connect(out);
  let nextT = c.currentTime + 0.1;
  let stepIdx = 0;
  const pattern = [0, 1, 2, 1, 2, 1, 0, 2];
  const live = [];

  function pluck(t, f, gain, dur) {
    tone(c, bus, t, { type: 'triangle', f, dur, gain, a: 0.004 });
    tone(c, bus, t, { type: 'sine', f: f * 2, dur: dur * 0.6, gain: gain * 0.35, a: 0.003 });
  }
  function pad(t, chord, len) {
    chord.forEach((n, i) => {
      [-6, 6].forEach(det => {
        const o = c.createOscillator();
        o.type = 'sawtooth';
        o.frequency.value = midi(n - 12);
        o.detune.value = det + i;
        const lp = c.createBiquadFilter();
        lp.type = 'lowpass'; lp.frequency.value = 520;
        const g = c.createGain();
        const pk = think ? 0.018 : 0.028;
        g.gain.setValueAtTime(0.0001, t);
        g.gain.linearRampToValueAtTime(pk, t + len * 0.35);
        g.gain.linearRampToValueAtTime(0.0001, t + len * 1.1);
        o.connect(lp).connect(g).connect(bus);
        o.start(t); o.stop(t + len * 1.15);
      });
    });
  }
  function schedule() {
    while (nextT < c.currentTime + 0.5) {
      const s8 = stepIdx % 8;
      const bar = Math.floor(stepIdx / 8) % prog.length;
      const d = prog[bar];
      const chord = [noteAt(d, 1), noteAt(d + 2, 1), noteAt(d + 4, 1)];
      if (s8 === 0) {
        pad(nextT, chord, step * 8);
        if (!think) pluck(nextT, midi(chord[0] - 24), 0.35, 0.5);
      }
      if (!think && s8 === 4) pluck(nextT, midi(chord[0] - 24), 0.25, 0.4);
      if (Math.random() > (think ? 0.55 : 0.12)) {
        const n = chord[pattern[s8]] + (s8 === 7 && Math.random() < 0.4 ? 12 : 0);
        pluck(nextT, midi(n), think ? 0.12 : 0.17, think ? 0.9 : 0.35);
      }
      // hand percussion (main only)
      if (!think) {
        if (s8 % 4 === 0) { tone(c, bus, nextT, { f: 130, f2: 80, dur: 0.12, gain: 0.18 }); }
        if (s8 % 2 === 1) noiseBurst(c, bus, nextT, { dur: 0.03, gain: 0.05, type: 'highpass', f: 6000 });
      }
      // celesta sparkle / clarinet-ish melody note
      if (Math.random() < (think ? 0.14 : 0.22)) {
        const mn = noteAt(pick([0, 2, 4, 5, 6, 7, 9]), 2);
        bell(c, bus, nextT + (Math.random() < 0.5 ? 0 : step * 0.5), midi(mn), 1.1, think ? 0.05 : 0.07, 4, 0.8);
      }
      if (!think && s8 === 0 && bar % 2 === 0) {
        [0, 2, 1, 3].forEach((dd, i) => {
          const f = midi(noteAt(d + dd + 2, 2));
          tone(c, bus, nextT + i * step * 1.5, { type: 'sawtooth', f, dur: step * 1.3, gain: 0.04, a: 0.05, lp: 1800 });
        });
      }
      nextT += step;
      stepIdx++;
    }
  }
  const timer = setInterval(schedule, 120);
  schedule();
  return { stop() { clearInterval(timer); try { bus.disconnect(); } catch (_) {} } };
}

function makeAmbience(c, out) {
  const bus = c.createGain();
  bus.connect(out);
  const nodes = [];
  // fire bed: low brown-ish rumble
  const s = c.createBufferSource();
  s.buffer = noiseBuffer(c); s.loop = true;
  const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 260;
  const g = c.createGain(); g.gain.value = 0.18;
  s.connect(lp).connect(g).connect(bus);
  s.start();
  nodes.push(s);
  const timer = setInterval(() => {
    const t = c.currentTime + 0.05;
    for (let i = 0; i < 3; i++) if (Math.random() < 0.6) {
      noiseBurst(c, bus, t + rnd(0, 0.25), { dur: rnd(0.008, 0.03), gain: rnd(0.04, 0.22), type: 'highpass', f: rnd(1500, 4500), q: 1 });
    }
    if (Math.random() < 0.05) { // cricket chirp train
      const f = rnd(4200, 4800);
      for (let k = 0; k < 4; k++) tone(c, bus, t + k * 0.07, { f, dur: 0.035, gain: 0.025, a: 0.004 });
    }
    if (Math.random() < 0.012) { // wooden creak
      const o = c.createOscillator(); o.type = 'sawtooth';
      o.frequency.setValueAtTime(rnd(90, 140), t);
      o.frequency.linearRampToValueAtTime(rnd(160, 230), t + 0.5);
      const bp = c.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 600; bp.Q.value = 6;
      const eg = envGain(c, t, 0.1, 0.5, 0.06);
      o.connect(bp).connect(eg).connect(bus);
      o.start(t); o.stop(t + 0.7);
    }
  }, 250);
  return { stop() { clearInterval(timer); nodes.forEach(n => { try { n.stop(); } catch (_) {} }); try { bus.disconnect(); } catch (_) {} } };
}

const GEN = { music_main: 'music', music_think: 'music', amb_workshop: 'amb' };

// ---------------------------------------------------------------------------
// Engine
// ---------------------------------------------------------------------------
class GolemAudio {
  constructor() {
    this.ctx = null;
    this.manifest = {};
    this.buffers = new Map();
    this._loading = new Map();
    this._failed = new Set();
    this._initP = null;
    this._muted = false;
    this.vols = { master: 0.9, music: 0.6, sfx: 0.9, vo: 1 };
    this._musicWanted = null;
    this._ambWanted = null;
    this._musicTrack = null;
    this._ambTrack = null;
    this._musicTok = 0;
    this._ambTok = 0;
    this._vo = null;
    this._duck = 0;
    this._lastVar = {};
    try {
      const s = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
      if (s) {
        this._muted = !!s.muted;
        for (const k of ['master', 'music', 'sfx', 'vo']) if (typeof s[k] === 'number') this.vols[k] = Math.min(1, Math.max(0, s[k]));
      }
    } catch (_) { /* ignore */ }
    if (typeof window !== 'undefined') {
      const wake = () => { if (this.ctx && this.ctx.state === 'suspended' && !document.hidden) this.ctx.resume().catch(() => {}); };
      ['pointerdown', 'keydown', 'touchend'].forEach(e => window.addEventListener(e, wake, { passive: true }));
      document.addEventListener('visibilitychange', () => {
        if (!this.ctx) return;
        if (document.hidden) this.ctx.suspend().catch(() => {});
        else this.ctx.resume().catch(() => {});
      });
    }
  }

  get muted() { return this._muted; }

  _save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify({ muted: this._muted, ...this.vols })); } catch (_) { /* ignore */ }
  }

  _applyVolumes() {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const set = (g, v) => g.gain.setTargetAtTime(v, t, 0.03);
    set(this.master, this._muted ? 0 : this.vols.master);
    set(this.musicBus, this.vols.music);
    set(this.sfxBus, this.vols.sfx);
    set(this.ambBus, this.vols.sfx);
    set(this.voBus, this.vols.vo);
  }

  setMuted(m) { this._muted = !!m; this._applyVolumes(); this._save(); }

  setVolumes(v = {}) {
    for (const k of ['master', 'music', 'sfx', 'vo']) if (typeof v[k] === 'number') this.vols[k] = Math.min(1, Math.max(0, v[k]));
    this._applyVolumes();
    this._save();
  }

  init() {
    if (this._initP) { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {}); return this._initP; }
    this._initP = this._init();
    return this._initP;
  }

  async _init() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    const c = (this.ctx = new AC({ latencyHint: 'interactive' }));
    this.master = c.createGain();
    this.comp = c.createDynamicsCompressor();
    this.comp.threshold.value = -14; this.comp.knee.value = 24; this.comp.ratio.value = 3;
    this.comp.attack.value = 0.01; this.comp.release.value = 0.25;
    this.masterIn = c.createGain();
    this.masterIn.connect(this.comp);
    this.comp.connect(this.master);
    this.master.connect(c.destination);
    this.musicBus = c.createGain();
    this.duckGain = c.createGain();
    this.sfxBus = c.createGain();
    this.voBus = c.createGain();
    this.ambBus = c.createGain();
    this.musicBus.connect(this.duckGain);
    this.duckGain.connect(this.masterIn);
    this.sfxBus.connect(this.masterIn);
    this.voBus.connect(this.masterIn);
    this.ambBus.connect(this.masterIn);
    // reverb: small stone room
    this.reverb = c.createConvolver();
    this.reverb.buffer = this._impulse(1.2);
    this.reverbIn = c.createGain();
    this.reverbOut = c.createGain();
    this.reverbOut.gain.value = 0.7;
    this.reverbIn.connect(this.reverb);
    this.reverb.connect(this.reverbOut);
    this.reverbOut.connect(this.masterIn);
    const vs = c.createGain(); vs.gain.value = 0.1;
    this.voBus.connect(vs).connect(this.reverbIn);
    this._applyVolumes();
    if (c.state === 'suspended') { try { await c.resume(); } catch (_) { /* ignore */ } }

    try {
      const r = await fetch(BASE + 'audio/manifest.json', { cache: 'no-cache' });
      if (r.ok) {
        const j = await r.json();
        if (j && typeof j === 'object') this.manifest = j;
      }
    } catch (_) { this.manifest = {}; }
    // preload sfx in the background
    for (const [id, m] of Object.entries(this.manifest)) if (m && m.kind === 'sfx') this._load(id);
    // apply requests made before init finished
    if (this._musicWanted) this.music(this._musicWanted.id, this._musicWanted.opts);
    if (this._ambWanted) this.ambience(this._ambWanted);
    return true;
  }

  _impulse(seconds) {
    const c = this.ctx;
    const len = Math.floor(c.sampleRate * seconds);
    const b = c.createBuffer(2, len, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = b.getChannelData(ch);
      let lp = 0;
      for (let i = 0; i < len; i++) {
        const t = i / len;
        const k = 0.15 + t * 0.7; // darker as it decays
        lp += (Math.random() * 2 - 1 - lp) * (1 - k);
        d[i] = lp * Math.pow(1 - t, 3) * (i < 200 ? i / 200 : 1) * 1.6;
      }
    }
    return b;
  }

  _load(id) {
    if (this.buffers.has(id)) return Promise.resolve(this.buffers.get(id));
    if (this._failed.has(id) || !this.manifest[id] || !this.ctx) return Promise.resolve(null);
    if (this._loading.has(id)) return this._loading.get(id);
    const p = (async () => {
      try {
        const r = await fetch(BASE + 'audio/' + this.manifest[id].file);
        if (!r.ok) throw new Error(String(r.status));
        const buf = await this.ctx.decodeAudioData(await r.arrayBuffer());
        this.buffers.set(id, buf);
        return buf;
      } catch (_) { this._failed.add(id); return null; }
      finally { this._loading.delete(id); }
    })();
    this._loading.set(id, p);
    return p;
  }

  _known() {
    const s = new Set(Object.keys(this.manifest));
    Object.keys(SYNTH).forEach(k => s.add(k));
    Object.keys(GEN).forEach(k => s.add(k));
    return s;
  }

  _resolve(id) {
    const known = this._known();
    if (known.has(id)) return { id, variant: false };
    const vars = [...known].filter(k => k.startsWith(id + '_') && /^\d+$/.test(k.slice(id.length + 1)));
    if (!vars.length) return null;
    let choice = pick(vars);
    if (vars.length > 1) while (choice === this._lastVar[id]) choice = pick(vars);
    this._lastVar[id] = choice;
    return { id: choice, variant: true };
  }

  play(id, { volume = 1, rate = 1, detune = 0, pan = 0, delay = 0 } = {}) {
    const c = this.ctx;
    if (!c || typeof id !== 'string') return null;
    const r = this._resolve(id);
    if (!r) return null;
    if (r.id.startsWith('vo_')) { this.vo(r.id); return null; }
    if (r.variant) rate *= 1 + rnd(-0.05, 0.05);
    const t = c.currentTime + Math.max(0, delay) + 0.005;
    const inp = c.createGain();
    inp.gain.value = volume;
    const panner = c.createStereoPanner ? c.createStereoPanner() : null;
    if (panner) { panner.pan.value = Math.max(-1, Math.min(1, pan)); inp.connect(panner); }
    const tail = panner || inp;
    tail.connect(this.sfxBus);
    const send = c.createGain(); send.gain.value = 0.14;
    tail.connect(send).connect(this.reverbIn);
    const pf = rate * Math.pow(2, detune / 1200);

    const m = this.manifest[r.id];
    const buf = m && this.buffers.get(r.id);
    if (buf) {
      const src = c.createBufferSource();
      src.buffer = buf;
      src.playbackRate.value = pf;
      const g = c.createGain(); g.gain.value = m.volume ?? 1;
      src.connect(g).connect(inp);
      src.start(t);
      return buf.duration / pf;
    }
    if (m && !this._failed.has(r.id)) this._load(r.id); // fetch for next time
    const fn = SYNTH[r.id];
    if (!fn) return null;
    try { return fn(c, inp, t, pf); } catch (_) { return null; }
  }

  // --- music / ambience (shared crossfading loop slot logic) ---
  async _startBed(kind, id, fade) {
    const c = this.ctx;
    const isMusic = kind === 'music';
    const tok = isMusic ? ++this._musicTok : ++this._ambTok;
    const out = isMusic ? this.musicBus : this.ambBus;
    const old = isMusic ? this._musicTrack : this._ambTrack;
    const stale = () => (isMusic ? this._musicTok : this._ambTok) !== tok;

    const fadeOut = tr => {
      if (!tr) return;
      const t = c.currentTime;
      tr.gain.gain.cancelScheduledValues(t);
      tr.gain.gain.setValueAtTime(tr.gain.gain.value, t);
      tr.gain.gain.linearRampToValueAtTime(0, t + fade);
      setTimeout(() => tr.stop(), fade * 1000 + 100);
    };
    if (isMusic) this._musicTrack = null; else this._ambTrack = null;
    fadeOut(old);
    if (!id) return;

    let track = null;
    const m = this.manifest[id];
    const gain = c.createGain();
    gain.gain.value = 0;
    gain.connect(out);
    const level = (m && m.volume) ?? 1;
    if (m) {
      const buf = await this._load(id);
      if (stale()) { gain.disconnect(); return; }
      if (buf) {
        const src = c.createBufferSource();
        src.buffer = buf; src.loop = true;
        src.connect(gain);
        src.start();
        track = { gain, stop() { try { src.stop(); } catch (_) {} try { gain.disconnect(); } catch (_) {} } };
      }
    }
    if (!track && GEN[id]) {
      const g = GEN[id] === 'amb' ? makeAmbience(c, gain) : makeMusic(c, gain, id);
      track = { gain, stop() { g.stop(); try { gain.disconnect(); } catch (_) {} } };
    }
    if (!track) { gain.disconnect(); return; }
    const t = c.currentTime;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(isMusic && !m ? 0.9 : level, t + fade);
    if (isMusic) this._musicTrack = track; else this._ambTrack = track;
  }

  music(id, { fade = 1.5 } = {}) {
    this._musicWanted = id ? { id, opts: { fade } } : null;
    if (!this.ctx) return;
    if (this._musicTrack && this._musicTrack.id === id) return;
    this._startBed('music', id, fade).then(() => { if (this._musicTrack) this._musicTrack.id = id; }).catch(() => {});
  }

  ambience(id) {
    this._ambWanted = id || null;
    if (!this.ctx) return;
    this._startBed('amb', id, 1.5).catch(() => {});
  }

  // --- voice-over ---
  _setDuck(on) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    this.duckGain.gain.setTargetAtTime(on ? 0.4 : 1, t, on ? 0.12 : 0.5); // ~ -8 dB
  }

  stopVo() {
    const v = this._vo;
    if (!v) return;
    this._vo = null;
    try { v.src && v.src.stop(); } catch (_) { /* ignore */ }
    clearTimeout(v.timer);
    this._setDuck(false);
    v.resolve();
  }

  vo(id) {
    this.stopVo();
    return new Promise(resolve => {
      const v = { resolve, src: null, timer: null };
      const finish = () => { if (this._vo === v) { this._vo = null; this._setDuck(false); } resolve(); };
      const silence = ms => { v.timer = setTimeout(finish, ms); };
      this._vo = v;
      const r = this.ctx ? this._resolve(id) : null;
      if (!this.ctx || !r || !this.manifest[r.id]) { silence(1200); return; }
      this._setDuck(true);
      this._load(r.id).then(buf => {
        if (this._vo !== v) return; // interrupted
        if (!buf) { silence(1200); return; }
        const c = this.ctx;
        const src = c.createBufferSource();
        src.buffer = buf;
        const g = c.createGain(); g.gain.value = this.manifest[r.id].volume ?? 1;
        src.connect(g).connect(this.voBus);
        src.onended = finish;
        v.src = src;
        src.start();
        // safety net: if the browser has audio suspended, 'ended' never fires and the game would wait forever
        v.timer = setTimeout(finish, buf.duration * 1000 + 800);
      });
    });
  }
}

export const audio = new GolemAudio();
export default audio;
