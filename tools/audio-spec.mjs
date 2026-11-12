// Audio spec for The Too-Literal Golem. Consumed by gen-audio.mjs.

// Configurable at the top. Default: "Bill - Wise, Mature, Balanced" (old, friendly storyteller; v4 is multilingual incl. Hebrew).
export const VOICE_ID = process.env.GOLEM_VOICE_ID || 'pqHfZKP75CvOlQylNhV4';
// Newest speech model with Hebrew support (verified via GET /v1/models); fallbacks tried in order.
export const TTS_MODELS = ['eleven_v4', 'eleven_v3'];
export const MUSIC_MODELS = ['music_v2_5', 'music_v2', 'music_v1'];
export const SFX_MODELS = ['eleven_text_to_sound_v3', 'eleven_text_to_sound_v2'];
export const VOICE_SETTINGS = { stability: 0.5, similarity_boost: 0.8, style: 0.35, speed: 0.9 };
export const VO_STYLE_PREFIX = ''; // e.g. audio tags; left empty to avoid being read aloud

const m = (id, prompt, seconds, loop, volume = 0.5) => ({ id, kind: 'music', prompt, seconds, loop, volume });
const a = (id, prompt, seconds, volume = 0.5) => ({ id, kind: 'amb', prompt, seconds, loop: true, volume });
const s = (id, prompt, seconds, volume = 0.8) => ({ id, kind: 'sfx', prompt, seconds, loop: false, volume });
const v = (id, text, volume = 1) => ({ id, kind: 'vo', text, loop: false, volume });

export const SPEC = [
  m('music_main', 'Instrumental. Cosy mystical night workshop, playful and curious, warm, not childish. Klezmer-tinged solo clarinet melody in a minor/freygish mode, plucky pizzicato strings, soft hand percussion (frame drum, shaker), twinkling celesta sparkles, gentle upright bass. Moderate walking tempo, steady groove, no big climax, seamlessly loopable.', 90, true, 0.5),
  m('music_think', 'Instrumental. Sparse, calm thinking music for solving a puzzle in a candlelit old workshop. Soft celesta and harp plucks, warm sustained pad, a distant gentle clarinet phrase now and then, very light brushed percussion. Klezmer-tinged minor scale, slow, patient, curious, quiet and unobtrusive, seamlessly loopable.', 60, true, 0.4),
  m('sting_success', 'Short triumphant warm fanfare with a playful clarinet flourish, pizzicato strings and bells ending on a bright major chord. Klezmer flavour, joyful, ends cleanly.', 4, false, 0.7),
  m('sting_fail', 'Short comedic deflating "wah-wah-wahhh" with a slow descending trombone and clarinet, gentle and friendly, not mocking, cartoon style, ends on a low note.', 3, false, 0.7),
  m('sting_final', 'Grand magical finale fanfare: swelling strings, soaring clarinet, shimmering celesta and harp glissando, timpani roll, warm triumphant resolution with a sparkling ending. Klezmer-tinged, wondrous and celebratory.', 8, false, 0.75),
  a('amb_workshop', 'Cosy night workshop ambience: gentle crackling fireplace, faint night crickets through a window, an occasional soft wooden creak. Calm, steady, seamless loop, no music.', 30, 0.5),
  ...[1, 2, 3].map(i => s(`step_${i}`, 'Single heavy stone golem footstep on a stone floor with a small pebble rattle, short, dry, close-up.', 0.6, 0.8)),
  s('turn', 'Heavy stone body grinding and swivelling on a stone floor, short scrape.', 0.8),
  s('bonk', 'Heavy stone body bumping into a wall, comedic hollow thud, one hit.', 1.0),
  s('bonk_books', 'Heavy thud against a bookshelf followed by several books toppling and thumping onto a wooden floor.', 1.8),
  s('pickup', 'Clay hands grabbing an object, soft scrape and gentle clay squeak.', 0.8),
  s('putdown', 'Gentle stone clunk of setting down a heavy object on a table.', 0.7),
  s('jug_smash', 'Clay jug shattering on a stone floor, pottery shards scattering.', 1.5),
  s('awaken', 'Magical rune ignition: a deep hum swelling into a shimmering chime, ancient magic awakening.', 1.5),
  s('sleep', 'Magical power-down hum fading away slowly, descending tone.', 1.0),
  s('stone_place', 'Small carved stone tile placed on a wooden tray, a satisfying crisp click.', 0.6),
  s('stone_remove', 'Small stone tile sliding off a wooden tray, short scrape.', 0.6),
  s('ui_tap', 'Soft wooden tap, a single light knock on wood.', 0.5, 0.7),
  s('fall', 'Cartoon whoosh of something falling into a deep pit, then a distant dull thud at the bottom.', 2.5),
  s('cat_meow', 'A single annoyed domestic cat meow.', 1.0),
  s('cat_purr', 'Short contented cat purr.', 1.5),
  s('plant_bloom', 'Magical sparkle growth swell, a plant blooming with glittering chimes rising.', 2.0),
  s('letter_collect', 'Warm golden chime, rising two-note magical pickup sound.', 0.8),
  s('candle_light', 'Match strike and a small flame whoosh igniting a candle wick.', 1.2),
  s('sweep', 'Straw broom sweeping across a stone floor, two strokes.', 1.2),
  s('star', 'Bright single bell ding, pure and sparkling, short ring.', 1.0),
  ...[1, 2, 3].map(i => s(`golem_grunt_${i}`, 'Short deep friendly rumbling grunt from a large stone creature, gravelly, warm, cartoon character vocalisation.', 0.8)),
  s('golem_huh', 'Deep confused questioning rumble from a stone creature, like "hmm?" with a rising inflection.', 1.0),
  s('golem_happy', 'Pleased deep rumbling chuckle from a stone creature, warm and gravelly.', 1.2),
  s('golem_oops', 'Embarrassed low "uh-oh" rumble from a stone creature, descending, sheepish.', 1.0),
  s('whoosh_ui', 'Soft page turn and air whoosh for a screen transition, gentle.', 0.6, 0.6),
  v('vo_intro', 'שלום, תלמיד יקר. כאן המאסטר. זה הגולם שלי. הוא חזק מאוד... אבל הוא עושה בדיוק, אבל בדיוק, מה שאומרים לו.'),
  v('vo_day1', 'החושך ירד. תגיד לגולם איך להגיע אל הנר, צעד אחרי צעד.'),
  v('vo_day2', 'הצמח שלי צמא. שהגולם ירים את הכד, ויניח אותו ליד העציץ.'),
  v('vo_day3', 'המסדרון ארוך, ויש לנו רק מעט אבנים. אולי אבן החזרה תעזור?'),
  v('vo_day4', 'שלוש אותיות התפזרו בחדר. אסוף את כולן, והמילה תתגלה.'),
  v('vo_day5', 'מבוך! הגולם לא רואה רחוק. למד אותו מה לעשות כשיש קיר.'),
  v('vo_fail_wall', 'אוי. הוא באמת הלך ישר לתוך הקיר.'),
  v('vo_fail_fall', 'הוא לא עצר. כי אף אחד לא אמר לו לעצור.'),
  v('vo_fail_cat', 'זה לא הכד. זה החתול.'),
  v('vo_fail_smash', 'הוא הניח אותו. בדיוק איפה שאמרת.'),
  v('vo_fail_generic', 'הממ. הוא עשה בדיוק מה שאמרת. נסה שוב.'),
  v('vo_fail_short', 'הוא סיים את כל ההוראות... ועדיין לא הגיע.'),
  v('vo_success_1', 'יפה מאוד!'),
  v('vo_success_2', 'בדיוק כך!'),
  v('vo_success_3', 'הגולם גאה בך.'),
  v('vo_final', 'אמת. עכשיו אתה יודע את הסוד: מי שנותן הוראות ברורות, יכול להזיז אפילו אבן.'),
  v('vo_tomorrow', 'מספיק להיום. הגולם צריך לנוח. נתראה מחר.'),
  v('vo_hint_repeat', 'אבן החזרה אומרת לגולם לעשות שוב ושוב את מה שבתוכה.'),
  v('vo_hint_if', 'אבן התנאי שואלת שאלה: יש קיר? אם כן, עושים דבר אחד. אם לא, דבר אחר.'),
];

// Loudness targets (integrated LUFS) per kind.
export const LUFS = { music: -18, sfx: -14, vo: -16, amb: -20 };
