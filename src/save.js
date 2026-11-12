// Progress + the "one new job per day" rule. Dev mode unlocks everything for testing.
const KEY = 'golem.save.v1';
const params = new URLSearchParams(location.search);
const today = () => new Date().toLocaleDateString('en-CA');

export const save = {
  data: { stars: {}, doneOn: {}, introSeen: false },
  // ?dev=1 switches test mode on and it stays on for later visits; ?dev=0 switches it off again.
  dev: (() => {
    const q = params.get('dev');
    if (q !== null) { try { localStorage.setItem('golem.dev', q === '0' ? '0' : '1'); } catch { /* ignore */ } return q !== '0'; }
    return params.has('day') || localStorage.getItem('golem.dev') === '1';
  })(),
  startDay: Math.min(5, Math.max(1, parseInt(params.get('day'), 10) || 0)) || null,
  load() { try { Object.assign(this.data, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch { /* fresh start */ } return this; },
  persist() { try { localStorage.setItem(KEY, JSON.stringify(this.data)); } catch { /* private mode */ } },
  setDev(on) { this.dev = on; try { localStorage.setItem('golem.dev', on ? '1' : '0'); } catch { /* ignore */ } },
  done(day) { return !!this.data.stars[day]; },
  doneCount() { return Object.keys(this.data.stars).length; },
  // A day is open when it was already solved, or it is the next one and the previous was solved before today.
  open(day) {
    if (this.dev || day === 1 || this.done(day)) return true;
    return this.done(day - 1) && this.data.doneOn[day - 1] !== today();
  },
  // The next job exists but only opens tomorrow.
  waiting(day) { return !this.dev && !this.done(day) && day > 1 && this.done(day - 1) && this.data.doneOn[day - 1] === today(); },
  current() { for (let d = 5; d >= 1; d--) if (this.open(d) && !this.done(d)) return d; return Math.min(5, this.doneCount() || 1); },
  win(day, stars) {
    this.data.stars[day] = Math.max(this.data.stars[day] || 0, stars);
    if (!this.data.doneOn[day]) this.data.doneOn[day] = today();
    this.persist();
  },
};
