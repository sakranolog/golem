// The five daily jobs. Map legend: '.' tile, ' ' no floor, '#' block, 'G' goal tile.
// start.dir: 0 north (away from camera), 1 east, 2 south, 3 west.
export const LEVELS = [
  {
    day: 1, name: 'אור ראשון', vo: 'vo_day1',
    brief: 'החושך ירד. תגיד לגולם איך להגיע אל הנר, צעד אחרי צעד.',
    map: [
      '#####',
      '#..G#',
      '#.   ',
      '#.   ',
      ' .   ',
    ],
    start: { x: 1, z: 4, dir: 0 },
    items: [], decor: [{ type: 'candle', x: 4, z: 1 }],
    goal: 'reach', palette: ['F', 'R', 'L'], slots: 8, par: 6,
    solution: 'F F F R F F',
  },
  {
    day: 2, name: 'הצמח הצמא', vo: 'vo_day2',
    brief: 'הצמח שלי צמא. שהגולם ירים את הכד, ויניח אותו ליד העציץ.',
    map: [
      '..G#',
      '... ',
      '... ',
    ],
    start: { x: 0, z: 2, dir: 1 },
    items: [{ type: 'jug', x: 0, z: 0 }, { type: 'cat', x: 2, z: 2 }],
    decor: [{ type: 'plant', x: 3, z: 0 }],
    goal: 'deliver', palette: ['F', 'R', 'L', 'P', 'D'], slots: 10, par: 8,
    solution: 'L F P R F F L D',
  },
  {
    day: 3, name: 'המסדרון הארוך', vo: 'vo_day3', hintVo: 'vo_hint_repeat',
    brief: 'המסדרון ארוך, ויש לנו רק מעט אבנים. אולי אבן החזרה תעזור?',
    map: [
      '....G',
      '.    ',
      '.    ',
      '.    ',
      '.    ',
      '.    ',
    ],
    start: { x: 0, z: 5, dir: 0 },
    items: [], decor: [],
    goal: 'reach', palette: ['F', 'R', 'L', 'REP'], slots: 6, par: 5,
    solution: 'REP5 F END R REP4 F END',
  },
  {
    day: 4, name: 'שלוש אותיות', vo: 'vo_day4',
    brief: 'שלוש אותיות התפזרו בחדר. אסוף את כולן, והמילה תתגלה.',
    map: [
      '...',
      '. .',
      '...',
    ],
    start: { x: 0, z: 2, dir: 0 },
    items: [
      { type: 'letter', letter: 'א', x: 0, z: 0 },
      { type: 'letter', letter: 'מ', x: 2, z: 0 },
      { type: 'letter', letter: 'ת', x: 2, z: 2 },
    ],
    decor: [],
    goal: 'collect', palette: ['F', 'R', 'L', 'REP'], slots: 5, par: 4,
    solution: 'REP3 F F R END',
  },
  {
    day: 5, name: 'המבוך', vo: 'vo_day5', hintVo: 'vo_hint_if',
    brief: 'מבוך! הגולם לא רואה רחוק. למד אותו מה לעשות כשיש קיר.',
    map: [
      '#######',
      '#.....#',
      '#.###.#',
      '#.#G#.#',
      '#.#.#.#',
      '#.#...#',
      '#######',
    ],
    start: { x: 1, z: 5, dir: 0 },
    items: [], decor: [],
    goal: 'reach', palette: ['F', 'R', 'L', 'REP', 'IF'], slots: 6, par: 4, infinite: true, final: true, lowWalls: true,
    solution: 'REP0 IF R ELSE F END END',
  },
];

// Turn a compact solution string into tokens (used by tests and the dev "solve" shortcut).
export function tokensFrom(str) {
  let id = 1;
  return str.split(/\s+/).map((w) => {
    const m = /^REP(\d)$/.exec(w);
    return m ? { t: 'REP', n: +m[1], id: id++ } : { t: w, id: id++ };
  });
}
