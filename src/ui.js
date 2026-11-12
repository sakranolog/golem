// DOM interface: stone tray, palette, narrator bubble, day chips, result panel.
import { stoneCount } from './interp.js';
import { LEVELS } from './levels.js';

const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const svg = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;

export const STONES = {
  F: { label: 'צעד', icon: svg('M12 20V5M5 12l7-7 7 7'), kind: 'move' },
  R: { label: 'ימינה', icon: svg('M6 20v-7a5 5 0 0 1 5-5h8M15 4l4 4-4 4'), kind: 'move' },
  L: { label: 'שמאלה', icon: svg('M18 20v-7a5 5 0 0 0-5-5H5M9 4L5 8l4 4'), kind: 'move' },
  P: { label: 'הרם', icon: svg('M12 14V4M8 8l4-4 4 4M5 14v5h14v-5'), kind: 'hand' },
  D: { label: 'הנח', icon: svg('M12 4v10M8 10l4 4 4-4M5 16v3h14v-3'), kind: 'hand' },
  REP: { label: 'חזור', icon: svg('M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3'), kind: 'loop' },
  IF: { label: 'יש קיר?', icon: svg('M3 5h18v14H3zM3 12h18M9 5v7M15 12v7'), kind: 'cond' },
  ELSE: { label: 'אחרת', icon: '', kind: 'cond', closer: true },
  END: { label: 'סוף', icon: '', kind: 'end', closer: true },
};
const DAY_NAMES = ['א׳', 'ב׳', 'ג׳', 'ד׳', 'ה׳'];

export class UI {
  constructor(handlers) {
    this.h = handlers; this.tokens = []; this.caret = 0; this.nextId = 1; this.locked = false;
    $('#go').addEventListener('click', () => !this.locked && this.h.run());
    $('#clear').addEventListener('click', () => { if (this.locked || !this.tokens.length) return; this.tokens = []; this.caret = 0; this.h.sound('stone_remove'); this.render(); });
    $('#mute').addEventListener('click', () => this.h.mute());
    $('#speed').addEventListener('click', () => this.h.speed());
    $('#solve').addEventListener('click', () => !this.locked && this.h.solve());
    $('#start').addEventListener('click', () => this.h.start());
    $('#again').addEventListener('click', () => this.h.again());
    $('#next').addEventListener('click', () => this.h.next());
    let taps = 0; $('#logo').addEventListener('click', () => { if (++taps === 5) { taps = 0; this.h.toggleDev(); } });
  }

  // ---------- program editing ----------
  setLevel(level) {
    this.level = level; this.tokens = []; this.caret = 0;
    $('#dayname').textContent = `יום ${DAY_NAMES[level.day - 1]} · ${level.name}`;
    const pal = $('#palette'); pal.innerHTML = '';
    for (const t of level.palette) {
      const b = this.stoneEl({ t, n: this.defaultN() }, true);
      b.addEventListener('click', () => this.insert(t)); pal.append(b);
    }
    $('#letters').innerHTML = ''; $('#letters').hidden = level.goal !== 'collect';
    if (level.goal === 'collect') for (let i = 0; i < 3; i++) $('#letters').append(el('span', 'slot'));
    this.render();
  }
  defaultN() { return this.level?.infinite ? 0 : 3; }
  matchEnd(i) { // index of the END closing the block opened at i
    let d = 0;
    for (let k = i; k < this.tokens.length; k++) { const t = this.tokens[k].t; if (t === 'REP' || t === 'IF') d++; else if (t === 'END' && --d === 0) return k; }
    return -1;
  }
  matchElse(i) { let d = 0; for (let k = i; k < this.tokens.length; k++) { const t = this.tokens[k].t; if (t === 'REP' || t === 'IF') d++; else if (t === 'END') d--; else if (t === 'ELSE' && d === 1) return k; } return -1; }
  insert(t) {
    if (this.locked) return;
    if (stoneCount(this.tokens) >= this.level.slots) { this.h.sound('ui_tap'); this.shake($('#count')); return; }
    const mk = (tt, n) => ({ t: tt, n, id: this.nextId++ });
    const add = t === 'REP' ? [mk('REP', this.defaultN()), mk('END')] : t === 'IF' ? [mk('IF'), mk('ELSE'), mk('END')] : [mk(t)];
    this.tokens.splice(this.caret, 0, ...add); this.caret += 1;
    this.h.sound('stone_place'); this.render(add[0].id);
  }
  tap(i) {
    if (this.locked) return;
    const tok = this.tokens[i];
    if (tok.t === 'END' || tok.t === 'ELSE') { this.caret = i + 1; this.h.sound('ui_tap'); return this.render(); }
    if (tok.t === 'REP' || tok.t === 'IF') {
      const e = this.matchEnd(i); const m = tok.t === 'IF' ? this.matchElse(i) : -1;
      for (const k of [e, m].filter((k) => k >= 0).sort((a, b) => b - a)) this.tokens.splice(k, 1);
    }
    this.tokens.splice(i, 1); this.caret = Math.min(i, this.tokens.length);
    this.h.sound('stone_remove'); this.render();
  }
  cycle(i, ev) {
    ev.stopPropagation(); if (this.locked) return;
    const tok = this.tokens[i]; const max = 9;
    tok.n = tok.n === 0 ? 2 : tok.n >= max ? (this.level.infinite ? 0 : 2) : tok.n + 1;
    this.h.sound('ui_tap'); this.render();
  }
  stoneEl(tok, palette = false) {
    const def = STONES[tok.t];
    const b = el('button', `stone k-${def.kind}${def.closer ? ' closer' : ''}`);
    b.type = 'button'; b.dataset.t = tok.t;
    b.innerHTML = `${def.icon ? `<i>${def.icon}</i>` : ''}<b>${def.label}</b>`;
    if (tok.t === 'REP' && !palette) { const n = el('span', 'n', tok.n === 0 ? '∞' : `×${tok.n}`); n.title = 'כמה פעמים?'; b.append(n); b._n = n; }
    return b;
  }
  render(popId) {
    const tray = $('#tray'); tray.innerHTML = '';
    let depth = 0;
    const gap = (i) => { const g = el('span', 'gap' + (i === this.caret ? ' caret' : '')); g.style.setProperty('--d', depth); g.addEventListener('click', () => { if (this.locked) return; this.caret = i; this.h.sound('ui_tap'); this.render(); }); tray.append(g); };
    this.tokens.forEach((tok, i) => {
      if (tok.t === 'END') depth--;
      const inner = tok.t === 'ELSE' ? depth - 1 : depth;
      gap(i);
      const b = this.stoneEl(tok); b.dataset.id = tok.id; b.style.setProperty('--d', Math.max(inner, 0)); if (inner > 0) b.classList.add('nested');
      if (tok.id === popId) b.classList.add('pop');
      b.addEventListener('click', () => this.tap(i));
      if (b._n) b._n.addEventListener('click', (ev) => this.cycle(i, ev));
      tray.append(b);
      if (tok.t === 'REP' || tok.t === 'IF') depth++;
    });
    gap(this.tokens.length);
    const left = this.level.slots - stoneCount(this.tokens);
    for (let i = 0; i < left; i++) tray.append(el('span', 'socket'));
    $('#count').textContent = left === 0 ? 'אין עוד אבנים' : left === 1 ? 'נשארה אבן אחת' : `נשארו ${left} אבנים`;
    $('#go').classList.toggle('ready', this.tokens.length > 0);
  }
  highlight(id) {
    for (const s of document.querySelectorAll('#tray .stone.active')) s.classList.remove('active');
    const s = id && document.querySelector(`#tray .stone[data-id="${id}"]`); if (s) { s.classList.add('active'); s.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' }); }
  }
  setLocked(on) { this.locked = on; document.body.classList.toggle('running', on); if (!on) this.highlight(null); }
  shake(node) { node.classList.remove('shake'); void node.offsetWidth; node.classList.add('shake'); }

  // ---------- narrator ----------
  say(text, mood = '') {
    const b = $('#bubble'); b.className = mood; b.hidden = false;
    const p = $('#bubble p'); p.innerHTML = '';
    text.split(' ').forEach((w, i) => { const s = el('span', '', w + ' '); s.style.animationDelay = `${i * 0.07}s`; p.append(s); });
  }
  hush() { $('#bubble').hidden = true; }

  // ---------- chrome ----------
  days(save, current) {
    const box = $('#days'); box.innerHTML = '';
    LEVELS.forEach((L) => {
      const open = save.open(L.day), stars = save.data.stars[L.day] || 0;
      const b = el('button', `day${L.day === current ? ' on' : ''}${open ? '' : ' locked'}${stars ? ' done' : ''}`);
      b.type = 'button'; b.innerHTML = `<b>${DAY_NAMES[L.day - 1]}</b><em>${open ? '★'.repeat(stars) + '<s>' + '★'.repeat(3 - stars) + '</s>' : save.waiting(L.day) ? 'מחר' : '·'}</em>`;
      b.title = open ? L.name : 'נפתח מחר';
      b.addEventListener('click', () => (open ? this.h.day(L.day) : this.shake(b)));
      box.append(b);
    });
    $('#solve').hidden = !save.dev; document.body.classList.toggle('dev', save.dev);
  }
  letter(ch, count) { const s = $('#letters').children[count - 1]; if (s) { s.textContent = ch; s.classList.add('got'); } }
  resetLetters() { for (const s of $('#letters').children) { s.textContent = ''; s.classList.remove('got'); } }
  setMuted(m) { $('#mute').classList.toggle('off', m); }
  setSpeed(fast) { $('#speed').classList.toggle('fast', fast); $('#speed b').textContent = fast ? '×2' : '×1'; }
  loading(p) { $('#loadbar i').style.width = `${Math.round(p * 100)}%`; }
  showTitle() { $('#loading').classList.add('gone'); $('#title').hidden = false; requestAnimationFrame(() => $('#title').classList.add('in')); }
  hideTitle() { $('#title').classList.remove('in'); setTimeout(() => { $('#title').hidden = true; }, 900); }
  showHud(on) { $('#hud').hidden = !on; requestAnimationFrame(() => $('#hud').classList.toggle('in', on)); }
  result({ stars, used, par, final, nextOpen, hasNext }) {
    const r = $('#result'); r.hidden = false; r.className = final ? 'final' : '';
    $('#result h2').textContent = final ? 'אמת!' : ['', 'הצלחת!', 'יפה מאוד!', 'מושלם!'][stars];
    $('#result .sub').textContent = final ? 'סיימת את כל חמשת הימים. הגולם שלך לנצח.' : stars === 3 ? `פתרת עם ${used} אבנים בלבד.` : `פתרת עם ${used} אבנים. אפשר גם עם ${par}!`;
    const box = $('#result .stars'); box.innerHTML = '';
    for (let i = 0; i < 3; i++) { const s = el('span', i < stars ? 'on' : '', '★'); s.style.animationDelay = `${0.25 + i * 0.28}s`; box.append(s); if (i < stars) setTimeout(() => this.h.sound('star', 1 + i * 0.12), 250 + i * 280); }
    $('#next').hidden = !hasNext || !nextOpen;
    $('#tomorrow').hidden = !hasNext || nextOpen;
    requestAnimationFrame(() => r.classList.add('in'));
  }
  hideResult() { const r = $('#result'); r.classList.remove('in'); r.hidden = true; }
}
