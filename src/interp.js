// Program model + simulator. Pure logic, no rendering.
// Directions: 0 = north (-Z, away from camera), 1 = east (+X), 2 = south, 3 = west.
export const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
export const MAX_ACTIONS = 70;

export function parse(tokens) {
  let i = 0;
  function block(stop) {
    const out = [];
    while (i < tokens.length) {
      const t = tokens[i];
      if (stop.includes(t.t)) return out;
      i++;
      if (t.t === 'REP') {
        const body = block(['END']);
        if (tokens[i]?.t === 'END') i++;
        out.push({ t: 'REP', n: t.n, id: t.id, body });
      } else if (t.t === 'IF') {
        const a = block(['ELSE', 'END']);
        let b = [];
        if (tokens[i]?.t === 'ELSE') { i++; b = block(['END']); }
        if (tokens[i]?.t === 'END') i++;
        out.push({ t: 'IF', id: t.id, a, b });
      } else if (t.t !== 'END' && t.t !== 'ELSE') out.push(t);
    }
    return out;
  }
  return block([]);
}

export function cellAt(level, x, z) {
  const row = level.map[z];
  if (!row || x < 0 || x >= row.length) return ' ';
  return row[x];
}

const BLOCKING = new Set(['cat', 'jug', 'plant', 'candle']);

// Returns { events, result } where result is 'win' or a failure kind.
export function simulate(level, tokens) {
  const prog = parse(tokens);
  const s = {
    x: level.start.x, z: level.start.z, dir: level.start.dir, holding: null,
    items: level.items.map((it, i) => ({ ...it, i, gone: false })), collected: 0, misplaced: false,
  };
  const events = [];
  let actions = 0;
  let result = null;
  const totalLetters = s.items.filter((it) => it.type === 'letter').length;
  const itemAt = (x, z) => s.items.find((it) => !it.gone && it.x === x && it.z === z);
  const front = () => [s.x + DIRS[s.dir][0], s.z + DIRS[s.dir][1]];
  const push = (ev) => events.push(ev);
  const end = (r) => { result = r; };

  function act(tok) {
    if (++actions > MAX_ACTIONS) { push({ type: 'dizzy', id: tok.id }); return end('dizzy'); }
    const id = tok.id;
    const [fx, fz] = front();
    const fc = cellAt(level, fx, fz);
    const fi = itemAt(fx, fz);
    switch (tok.t) {
      case 'L': case 'R':
        s.dir = (s.dir + (tok.t === 'R' ? 1 : 3)) % 4;
        push({ type: 'turn', id, right: tok.t === 'R', dir: s.dir });
        break;
      case 'F':
        if (fc === '#') { push({ type: 'bonk', id, x: fx, z: fz }); return end('wall'); }
        if (fc === ' ') { push({ type: 'trip', id, x: fx, z: fz }); return end('fall'); }
        if (fi && BLOCKING.has(fi.type)) {
          if (fi.type === 'jug') { push({ type: 'kick', id, item: fi.i, x: fx, z: fz }); return end('smash'); }
          if (fi.type === 'cat') { push({ type: 'bumpcat', id, item: fi.i, x: fx, z: fz }); return end('catbump'); }
          push({ type: 'bonk', id, x: fx, z: fz }); return end('wall');
        }
        s.x = fx; s.z = fz;
        push({ type: 'step', id, x: fx, z: fz });
        if (fi && fi.type === 'letter') {
          fi.gone = true; s.collected++;
          push({ type: 'collect', id, item: fi.i, letter: fi.letter, count: s.collected });
          if (level.goal === 'collect' && s.collected === totalLetters) return end('win');
        }
        if (level.goal === 'reach' && fc === 'G') return end('win');
        break;
      case 'P':
        if (s.holding !== null) { push({ type: 'shrug', id }); break; }
        if (!fi || fi.type === 'letter' || fi.type === 'plant' || fi.type === 'candle') { push({ type: 'grabair', id }); break; }
        fi.gone = true; s.holding = fi.i;
        push({ type: 'pickup', id, item: fi.i, kind: fi.type });
        if (fi.type === 'cat') return end('cat');
        break;
      case 'D': {
        if (s.holding === null) { push({ type: 'shrug', id }); break; }
        const it = s.items[s.holding];
        if (fc === '#' || fc === ' ' || fi) { push({ type: 'dropsmash', id, item: it.i, x: fx, z: fz }); s.holding = null; return end('smash'); }
        it.gone = false; it.x = fx; it.z = fz; s.holding = null;
        push({ type: 'put', id, item: it.i, x: fx, z: fz });
        if (level.goal === 'deliver') { if (fc === 'G') return end('win'); s.misplaced = true; }
        break;
      }
    }
  }

  function run(nodes) {
    for (const n of nodes) {
      if (result) return;
      if (n.t === 'REP') {
        const count = n.n === 0 ? Infinity : n.n;
        for (let k = 0; k < count && !result; k++) {
          push({ type: 'loop', id: n.id, k: k + 1, n: n.n });
          if (!n.body.length) { if (++actions > MAX_ACTIONS) { push({ type: 'dizzy', id: n.id }); end('dizzy'); } continue; }
          run(n.body);
        }
      } else if (n.t === 'IF') {
        const [fx, fz] = front();
        const fi = itemAt(fx, fz);
        const blocked = cellAt(level, fx, fz) === '#' || !!(fi && BLOCKING.has(fi.type));
        if (++actions > MAX_ACTIONS) { push({ type: 'dizzy', id: n.id }); return end('dizzy'); }
        push({ type: 'sense', id: n.id, blocked });
        run(blocked ? n.a : n.b);
      } else act(n);
    }
  }
  run(prog);
  if (!result) result = s.misplaced ? 'misplaced' : 'short';
  if (result === 'win') push({ type: 'win' });
  return { events, result };
}

// Count the stones the player actually chose (closers are automatic).
export const stoneCount = (tokens) => tokens.filter((t) => t.t !== 'END' && t.t !== 'ELSE').length;
