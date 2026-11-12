import '@fontsource/fredoka/500.css';
import '@fontsource/fredoka/600.css';
import '@fontsource/fredoka/700.css';
import '@fontsource/rubik/400.css';
import '@fontsource/rubik/500.css';
import '@fontsource/rubik/700.css';
import './style.css';
import { World } from './world.js';
import { UI } from './ui.js';
import { LEVELS, tokensFrom } from './levels.js';
import { simulate, stoneCount } from './interp.js';
import { audio } from './audio.js';
import { save } from './save.js';

const TEXT = {
  vo_intro: 'שלום, תלמיד יקר. כאן המאסטר. זה הגולם שלי. הוא חזק מאוד... אבל הוא עושה בדיוק, אבל בדיוק, מה שאומרים לו.',
  vo_fail_wall: 'אוי. הוא באמת הלך ישר לתוך הקיר.',
  vo_fail_fall: 'הוא לא עצר. כי אף אחד לא אמר לו לעצור.',
  vo_fail_cat: 'זה לא הכד. זה החתול.',
  vo_fail_smash: 'הוא הניח אותו. בדיוק איפה שאמרת.',
  vo_fail_generic: 'הממ. הוא עשה בדיוק מה שאמרת. נסה שוב.',
  vo_fail_short: 'הוא סיים את כל ההוראות... ועדיין לא הגיע.',
  vo_success_1: 'יפה מאוד!', vo_success_2: 'בדיוק כך!', vo_success_3: 'הגולם גאה בך.',
  vo_final: 'אמת. עכשיו אתה יודע את הסוד: מי שנותן הוראות ברורות, יכול להזיז אפילו אבן.',
  vo_tomorrow: 'מספיק להיום. הגולם צריך לנוח. נתראה מחר.',
  vo_hint_repeat: 'אבן החזרה אומרת לגולם לעשות שוב ושוב את מה שבתוכה.',
  vo_hint_if: 'אבן התנאי שואלת שאלה: יש קיר? אם כן, עושים דבר אחד. אם לא, דבר אחר.',
};
const FAIL_VO = { wall: 'vo_fail_wall', fall: 'vo_fail_fall', cat: 'vo_fail_cat', misplaced: 'vo_fail_smash', short: 'vo_fail_short' };

save.load();
const world = new World(document.getElementById('c'));
let level = null, fails = 0, busy = false, fast = false, sayToken = 0;

const lock = (on) => { ui.setLocked(on); world.interactive = !on; if (on) world.releaseGrab(); };

async function narrate(id, text = TEXT[id], mood = '') {
  const my = ++sayToken; ui.say(text, mood);
  await audio.vo(id);
  return my === sayToken;
}

const ui = new UI({
  sound: (id, rate = 1) => audio.play(id, { rate }),
  mute: () => { audio.setMuted(!audio.muted); ui.setMuted(audio.muted); },
  speed: () => { fast = !fast; world.speed = fast ? 2.2 : 1; ui.setSpeed(fast); audio.play('ui_tap'); },
  toggleDev: () => { save.setDev(!save.dev); ui.days(save, level?.day); audio.play('star'); },
  solve: () => { if (!ui.level) return; ui.tokens = tokensFrom(level.solution).map((t) => ({ ...t, id: ui.nextId++ })); ui.caret = ui.tokens.length; ui.render(); },
  start, run, day: (d) => !busy && openDay(d),
  again: () => { ui.hideResult(); openDay(level.day); },
  next: () => { ui.hideResult(); openDay(level.day + 1); },
});

async function boot() {
  await world.init((p) => ui.loading(p));
  level = LEVELS[(save.startDay || save.current()) - 1];
  await world.loadLevel(level, { instant: true });
  world.setCinematic(true);
  ui.setMuted(audio.muted);
  ui.showTitle();
  window.__golem = { world, ui, save, audio, LEVELS }; // handy for testing
}

async function start() {
  if (busy || !level) return; busy = true;
  await audio.init();
  ui.setMuted(audio.muted);
  audio.play('whoosh_ui'); audio.ambience('amb_workshop'); audio.music('music_main');
  ui.hideTitle(); ui.showHud(true); document.body.classList.add('intro');
  if (!save.data.introSeen || save.startDay === null && save.doneCount() === 0) {
    await world.wait(0.6);
    world.gv('eye', 0.5, 1.2);
    await narrate('vo_intro');
    save.data.introSeen = true; save.persist();
  }
  document.body.classList.remove('intro');
  world.setCinematic(false);
  busy = false;
  openDay(level.day, true);
}

async function openDay(day, first = false) {
  if (busy) return; busy = true;
  level = LEVELS[day - 1]; fails = 0;
  lock(true); ui.setLevel(level); ui.days(save, day); ui.hideResult();
  audio.music('music_think');
  if (!first) audio.play('whoosh_ui');
  const loading = world.loadLevel(level);
  narrate(level.vo, level.brief);
  await loading;
  lock(false); busy = false;
}

async function run() {
  if (busy) return; busy = true;
  sayToken++; audio.stopVo(); ui.hush(); lock(true); ui.resetLetters();
  const tokens = ui.tokens.map((t) => ({ ...t }));
  const { events, result } = simulate(level, tokens);
  await world.awaken();
  await world.play(events, (ev) => { ui.highlight(ev.id); if (ev.type === 'collect') ui.letter(ev.letter, ev.count); });
  ui.highlight(null);
  if (result === 'win') return win(tokens);

  fails++;
  if (!['wall', 'fall', 'cat', 'catbump', 'smash', 'dizzy'].includes(result)) { await world.ev_shrug(); }
  audio.play('sting_fail', { volume: 0.8 });
  const voId = FAIL_VO[result] || 'vo_fail_generic';
  const spoke = narrate(voId, TEXT[voId], 'oops');
  await Promise.all([spoke, world.wait(1.4)]);
  await world.sleep(); await world.resetRun(); ui.resetLetters();
  lock(false); busy = false;
  if (fails === 2 && level.hintVo) narrate(level.hintVo, TEXT[level.hintVo], 'hint');
  else if (fails >= 2) ui.say(level.brief);
}

async function win(tokens) {
  const used = stoneCount(tokens);
  const stars = used <= level.par ? 3 : used <= level.par + 2 ? 2 : 1;
  save.win(level.day, stars);
  audio.music('music_main');
  audio.play(level.final ? 'sting_final' : 'sting_success');
  const voId = level.final ? 'vo_final' : `vo_success_${1 + Math.floor(Math.random() * 3)}`;
  narrate(voId, TEXT[voId], 'yay');
  await world.wait(level.final ? 1.6 : 0.9);
  ui.days(save, level.day);
  const hasNext = level.day < LEVELS.length; const nextOpen = hasNext && save.open(level.day + 1);
  ui.result({ stars, used, par: level.par, final: !!level.final, hasNext, nextOpen });
  busy = false;
  if (hasNext && !nextOpen) { await world.wait(2.4); if (!document.getElementById('result').hidden) narrate('vo_tomorrow', TEXT.vo_tomorrow); }
}

boot();
