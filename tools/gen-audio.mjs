#!/usr/bin/env node
// Generates all game audio via ElevenLabs into public/audio. Usage:
//   node tools/gen-audio.mjs [--force] [--only <id>]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { SPEC, VOICE_ID, TTS_MODELS, MUSIC_MODELS, SFX_MODELS, VOICE_SETTINGS, LUFS } from './audio-spec.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'public/audio');
const FFMPEG = '/opt/homebrew/bin/ffmpeg';
const API = 'https://api.elevenlabs.io';

const env = fs.existsSync(path.join(ROOT, '.env')) ? fs.readFileSync(path.join(ROOT, '.env'), 'utf8') : '';
const KEY = (env.match(/^\s*ELEVENLABS_API_KEY\s*=\s*(.*)$/m)?.[1] || process.env.ELEVENLABS_API_KEY || '').trim().replace(/^["']|["']$/g, '');
if (!KEY) { console.log('ELEVENLABS_API_KEY is empty or missing in .env - skipping audio generation. The game will use procedural fallback sounds.'); process.exit(0); }

const args = process.argv.slice(2);
const FORCE = args.includes('--force');
const onlyIdx = args.indexOf('--only');
const ONLY = onlyIdx >= 0 ? args[onlyIdx + 1] : null;
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function post(url, body, tries = 6) {
  for (let i = 0; i < tries; i++) {
    let res;
    try { res = await fetch(API + url, { method: 'POST', headers: { 'xi-api-key': KEY, 'Content-Type': 'application/json', Accept: 'audio/mpeg' }, body: JSON.stringify(body) }); }
    catch (e) { await sleep(2000 * (i + 1)); continue; }
    if (res.ok) return Buffer.from(await res.arrayBuffer());
    if (res.status === 429 || res.status >= 500) { await sleep(Math.min(30000, 2000 * 2 ** i)); continue; }
    const err = new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`); err.status = res.status; throw err;
  }
  throw new Error('retries exhausted');
}
// Try models in order; move to the next on 4xx (unknown model / not permitted).
async function withModels(models, fn) {
  let last;
  for (const m of models) { try { return await fn(m); } catch (e) { last = e; if (!e.status || e.status < 400 || e.status >= 500 || e.status === 401) throw e; } }
  throw last;
}

function generate(it) {
  if (it.kind === 'vo') return withModels(TTS_MODELS, model => post(`/v1/text-to-speech/${VOICE_ID}?output_format=mp3_44100_128`, { text: it.text, model_id: model, language_code: 'he', voice_settings: VOICE_SETTINGS }).catch(e => {
    if (e.status === 422 || e.status === 400) return post(`/v1/text-to-speech/${VOICE_ID}?output_format=mp3_44100_128`, { text: it.text, model_id: model, voice_settings: VOICE_SETTINGS });
    throw e; }));
  if (it.kind === 'music') return withModels(MUSIC_MODELS, model => post('/v1/music?output_format=mp3_44100_128', { prompt: it.prompt, music_length_ms: Math.round(it.seconds * 1000), force_instrumental: true, model_id: model }));
  return withModels(SFX_MODELS, model => post('/v1/sound-generation?output_format=mp3_44100_128', { text: it.prompt, duration_seconds: it.seconds, prompt_influence: 0.5, loop: !!it.loop, model_id: model }));
}

const FFPROBE = '/opt/homebrew/bin/ffprobe';
const duration = f => parseFloat(execFileSync(FFPROBE, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).toString());

function normalise(raw, dest, it) {
  const I = LUFS[it.kind];
  const enc = ['-ar', '44100', '-ac', it.kind === 'sfx' ? '1' : '2', '-b:a', '128k', dest];
  const ln = `loudnorm=I=${I}:TP=-1.5:LRA=11`;
  if (it.kind === 'music' && it.loop) {
    // Seamless loop: crossfade the last X seconds into the start.
    const X = 2, D = duration(raw);
    execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', raw, '-filter_complex',
      `[0]atrim=${D - X}:${D},asetpts=PTS-STARTPTS[t];[0]atrim=0:${D - X},asetpts=PTS-STARTPTS[h];[t][h]acrossfade=d=${X}:c1=tri:c2=tri,${ln}`, ...enc]);
    return;
  }
  if (it.kind === 'music') { // stings: cut to the requested length (models sometimes run long) with a short fade-out
    const T = Math.min(duration(raw), it.seconds + 0.2);
    execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', raw, '-af', `atrim=0:${T},afade=t=out:st=${Math.max(0, T - 0.4)}:d=0.4,${ln}`, ...enc]);
    return;
  }
  const run = trim => {
    const filters = [];
    if (trim) filters.push('silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.01:detection=peak');
    filters.push(ln);
    execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', raw, '-af', filters.join(','), ...enc]);
  };
  const wantTrim = it.kind === 'sfx' || it.kind === 'vo';
  try { run(wantTrim); if (fs.statSync(dest).size < 1500 && wantTrim) run(false); } catch { run(false); }
}

const items = SPEC.filter(it => !ONLY || it.id === ONLY);
if (ONLY && !items.length) { console.error('Unknown id', ONLY); process.exit(1); }
const tmp = fs.mkdtempSync(path.join(OUT, '.tmp-'));
let done = 0, skipped = 0, failed = [];
for (const it of items) {
  const dest = path.join(OUT, `${it.id}.mp3`);
  if (fs.existsSync(dest) && !FORCE) { skipped++; continue; }
  try {
    process.stdout.write(`generating ${it.id} ... `);
    const buf = await generate(it);
    const raw = path.join(tmp, `${it.id}.raw.mp3`);
    fs.writeFileSync(raw, buf);
    normalise(raw, dest, it);
    done++; console.log('ok');
  } catch (e) { failed.push(it.id); console.log('FAILED', e.message); }
}
if (!process.env.KEEP) fs.rmSync(tmp, { recursive: true, force: true });

const manifest = {};
for (const it of SPEC) if (fs.existsSync(path.join(OUT, `${it.id}.mp3`))) manifest[it.id] = { file: `${it.id}.mp3`, kind: it.kind, loop: !!it.loop, volume: it.volume ?? 1 };
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`done: ${done} generated, ${skipped} skipped, ${failed.length} failed${failed.length ? ' (' + failed.join(', ') + ')' : ''}; manifest has ${Object.keys(manifest).length} entries`);
