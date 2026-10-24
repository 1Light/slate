const BORROWED = {
  el, chapter, withTitles, nameList, letterFor, settleInto, failure,
};
const missing = Object.entries(BORROWED)
  .filter(([, v]) => typeof v !== 'function')
  .map(([k]) => k);
if (missing.length) {
  document.body.textContent = 'Slate could not start: app.js is missing '
    + `${missing.join(', ')}.`;
  throw new Error(`work.js needs ${missing.join(', ')} from app.js`);
}

const stage = document.getElementById('stage');
const here = document.querySelector('.deskbar-here');
const end = document.querySelector('.deskbar-end');

const OWNER_KEY = 'slate.owner.v1';

function owner() {
  let id = null;
  try {
    id = window.localStorage.getItem(OWNER_KEY);
  } catch {
    id = null;
  }
  if (!id || id.length < 8) {
    id = (crypto.randomUUID
      ? crypto.randomUUID().replace(/-/g, '')
      : Math.random().toString(36).slice(2).repeat(3)).slice(0, 32);
    try {
      window.localStorage.setItem(OWNER_KEY, id);
    } catch {
    }
  }
  return id;
}

async function ask(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let why = `${res.status}`;
    try {
      const body = await res.json();
      why = body.detail || body.error || why;
    } catch {  }
    throw new Error(why);
  }
  return res.json();
}

const AGO = [
  [60, 'just now'], [3600, 'in the last hour'], [86400, 'today'],
  [172800, 'yesterday'], [604800, 'this week'],
];

function ago(at) {
  const gap = Date.now() / 1000 - at;
  for (const [limit, said] of AGO) if (gap < limit) return said;
  return new Date(at * 1000).toLocaleDateString('en-GB',
    { day: 'numeric', month: 'short' });
}

const NOUN = {
  'urn:entity:movie': ['film', 'films'],
  'urn:entity:tv_show': ['show', 'shows'],
  'urn:entity:artist': ['act', 'acts'],
  'urn:entity:book': ['book', 'books'],
  'urn:entity:podcast': ['podcast', 'podcasts'],
};

const nounFor = (kind, n) => (NOUN[kind] || ['title', 'titles'])[n === 1 ? 0 : 1];

let spaces = [];

async function load() {
  try {
    const got = await ask(`/api/spaces?owner=${owner()}`);
    spaces = got.spaces || [];
  } catch {
    spaces = [];
  }
  draw();
}

const SAMPLE = {
  bar: [4, 3, 2],
  groups: [
    { letter: 'A', n: 4, films: [['Anatomy of a Fall'], ['The Zone of Interest']], more: 2 },
    { letter: 'B', n: 3, films: [['Perfect Days'], ['Fallen Leaves', 'bridge B\u00b7C', 'bridge']] },
    { letter: 'C', n: 2, films: [['Youth'], ['Monster', 'outlier', 'alone']] },
  ],
};

function sampleFigure() {
  const fig = el('div', 'taste');
  const bar = el('div', 'taste-bar');
  SAMPLE.bar.forEach((w, i) => {
    const seg = el('span');
    seg.style.flex = String(w);
    if (i === 0) seg.classList.add('lead');
    bar.appendChild(seg);
  });
  fig.appendChild(bar);

  const cols = el('div', 'taste-cols');
  SAMPLE.groups.forEach((g) => {
    const col = el('div');
    const head = el('p', 'taste-head');
    head.appendChild(el('span', 'taste-letter', g.letter));
    head.appendChild(el('span', 'taste-n', String(g.n)));
    col.appendChild(head);
    g.films.forEach(([title, tag, kind]) => {
      const row = el('p', kind ? `taste-film ${kind}` : 'taste-film');
      row.appendChild(document.createTextNode(title));
      if (tag) {
        row.appendChild(document.createElement('br'));
        row.appendChild(el('span', `taste-tag ${kind}`, tag));
      }
      col.appendChild(row);
    });
    if (g.more) col.appendChild(el('p', 'taste-more', `+${g.more}`));
    cols.appendChild(col);
  });
  fig.appendChild(cols);
  return fig;
}

function draw() {
  here.textContent = '';
  end.textContent = '';
  stage.textContent = '';

  const top = el('div', 'door');

  const left = el('div', 'door-ask');
  left.appendChild(el('h1', 'door-title', 'Start with a lineup.'));
  left.appendChild(el('p', 'door-lede',
    'Four to twenty-four titles, one per line. Films, music, books, '
    + 'podcasts or TV shows.'));

  const area = el('textarea');
  area.rows = 7;
  area.spellcheck = false;
  area.placeholder = 'Anatomy of a Fall\nPerfect Days\nThe Zone of Interest\n'
    + 'Fallen Leaves\nYouth (2023)';
  left.appendChild(area);

  const row = el('div', 'row');
  const make = el('button', 'solid', 'Make a workspace');
  make.type = 'button';
  const sample = el('button', 'linky', 'Use an example');
  sample.type = 'button';
  row.append(make, sample);
  left.appendChild(row);

  const said = el('p', 'door-said');
  said.setAttribute('role', 'status');
  said.setAttribute('aria-live', 'polite');
  left.appendChild(said);

  const right = el('div', 'door-show');
  right.appendChild(sampleFigure());
  right.appendChild(el('p', 'door-caption', 'What Slate gives back'));

  top.append(left, right);
  stage.appendChild(top);

  make.onclick = async () => {
    const titles = area.value.split('\n').map((t) => t.trim()).filter(Boolean);
    if (titles.length < 4) {
      said.textContent = 'Four titles at least, so there is something to '
        + 'separate.';
      return;
    }
    make.disabled = true;
    make.textContent = 'Working it out';
    said.textContent = '';
    try {
      const made = await ask('/api/spaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner: owner(), titles }),
      });
      window.location.href = `/app#${made.id}`;
      window.location.reload();
    } catch (e) {
      said.textContent = e.message || 'That did not work.';
    } finally {
      make.disabled = false;
      make.textContent = 'Make a workspace';
    }
  };

  let lastPick = null;
  sample.onclick = async () => {
    try {
      const got = await ask('/api/examples');
      const pool = (got.examples || []).filter((x) => x.slug !== lastPick);
      if (!pool.length) return;
      const pick = pool[Math.floor(Math.random() * pool.length)];
      lastPick = pick.slug;
      area.value = pick.titles.join('\n');
      said.textContent = pick.name;
    } catch {
      said.textContent = 'No examples are loaded.';
    }
  };

  if (!spaces.length) return;

  const band = el('div', 'door-band');
  const inner = el('div', 'door-band-in');
  inner.appendChild(el('p', 'door-head', 'Earlier workspaces'));
  const cards = el('div', 'door-cards');
  spaces.forEach((w) => cards.appendChild(spaceRow(w)));
  inner.appendChild(cards);
  band.appendChild(inner);
  stage.appendChild(band);
}

function spaceRow(w) {
  const card = el('div', 'door-card');

  const open = el('button', 'door-card-open');
  open.type = 'button';

  const bar = el('div', 'door-card-bar');
  (w.sizes && w.sizes.length ? w.sizes : [1]).forEach((n, i) => {
    const seg = el('span');
    seg.style.flex = String(Math.max(1, n));
    if (i === 0) seg.classList.add('lead');
    bar.appendChild(seg);
  });
  open.appendChild(bar);

  open.appendChild(el('p', 'door-card-name', w.name));
  const n = w.titles.length;
  open.appendChild(el('p', 'door-card-what',
    `${n} ${nounFor(w.entity_type, n)}`
    + (w.groups ? ` \u00b7 ${w.groups} groups` : '')));
  open.appendChild(el('p', 'door-card-when',
    `${w.versions ? `${w.versions} version${w.versions === 1 ? '' : 's'}`
      : 'no versions'} \u00b7 ${ago(w.touched)}`));
  open.onclick = () => {
    window.location.href = `/app#${w.id}`;
    window.location.reload();
  };
  card.appendChild(open);

  const more = el('button', 'door-card-more', '\u22ee');
  more.type = 'button';
  more.setAttribute('aria-label', `More for ${w.name}`);
  more.setAttribute('aria-expanded', 'false');
  card.appendChild(more);

  const menu = el('div', 'space-menu');
  menu.hidden = true;

  const rename = el('button', null, 'Rename');
  rename.type = 'button';
  rename.onclick = async (ev) => {
    ev.stopPropagation();
    menu.hidden = true;
    const want = window.prompt('Call it what?', w.name);
    if (!want || want === w.name) return;
    await ask(`/api/spaces/${w.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner: owner(), name: want }),
    });
    load();
  };

  const bin = el('button', 'danger', 'Delete');
  bin.type = 'button';
  bin.onclick = async (ev) => {
    ev.stopPropagation();
    menu.hidden = true;
    if (!window.confirm(`Delete ${w.name}? Its versions go too.`)) return;
    await ask(`/api/spaces/${w.id}?owner=${owner()}`, { method: 'DELETE' });
    load();
  };

  menu.append(rename, bin);
  card.appendChild(menu);

  more.onclick = (ev) => {
    ev.stopPropagation();
    const show = menu.hidden;
    document.querySelectorAll('.space-menu').forEach((m) => { m.hidden = true; });
    document.querySelectorAll('.door-card-more').forEach((b) => {
      b.setAttribute('aria-expanded', 'false');
    });
    menu.hidden = !show;
    more.setAttribute('aria-expanded', String(show));
  };

  return card;
}

document.addEventListener('click', () => {
  document.querySelectorAll('.space-menu').forEach((m) => { m.hidden = true; });
  document.querySelectorAll('.space-more').forEach((b) => {
    b.setAttribute('aria-expanded', 'false');
  });
});

document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  document.querySelectorAll('.space-menu').forEach((m) => { m.hidden = true; });
});

let space = null;
let started = null;
let shown = null;
let asked = 0;

const lineup = () => (space ? space.titles.slice() : []);

async function openSpace(id) {
  try {
    space = await ask(`/api/spaces/${id}?owner=${owner()}`);
  } catch {
    window.location.hash = '';
    load();
    return;
  }
  started = space.titles.slice();
  drawSpace();
  runSpace();
}

async function save(fields) {
  try {
    space = await ask(`/api/spaces/${space.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner: owner(), ...fields }),
    });
  } catch {  }
}

let rail;
let figure;
let work;
let feet;
let status;
let slotField;
let chipBox;
let versionBox;
let openAsk = null;
let chipsOpen = false;

const ASKS = [
  ['fewer', 'Fit it into fewer slots'],
  ['swap', 'Find a title that adds a new group'],
  ['stand', 'Check a new title against the lineup'],
  ['compare', 'Compare titles before adding'],
];

function drawSpace() {
  stage.textContent = '';
  here.textContent = '';
  end.textContent = '';
  openAsk = null;
  chipsOpen = false;

  const title = el('span', 'deskbar-name', space.name);
  title.contentEditable = 'plaintext-only';
  title.spellcheck = false;
  title.setAttribute('role', 'textbox');
  title.setAttribute('aria-label', 'Workspace name');
  title.title = 'Click to rename';
  title.onblur = async () => {
    const want = title.textContent.trim();
    if (!want) { title.textContent = space.name; return; }
    if (want === space.name) return;
    await save({ name: want });
    title.textContent = space.name;
    status.textContent = 'Renamed';
  };
  title.onkeydown = (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); title.blur(); }
    if (ev.key === 'Escape') { title.textContent = space.name; title.blur(); }
  };
  here.appendChild(el('span', 'deskbar-slash', '\u00a0/\u00a0'));
  here.appendChild(title);

  end.appendChild(el('span', 'deskbar-counts'));

  const resetBtn = el('button', 'ghost', 'Reset lineup');
  resetBtn.type = 'button';
  resetBtn.hidden = true;
  resetBtn.onclick = async () => {
    await save({ titles: started.slice() });
    drawChips();
    drawSpace.drawKeep();
    runSpace();
    status.textContent = 'Back to the lineup you started with.';
  };

  const printBtn = el('button', 'ghost', 'Preview');
  printBtn.type = 'button';
  printBtn.onclick = () => {
    if (!shown) { status.textContent = 'Nothing to show yet.'; return; }
    openAsk = 'paper';
    markAsk();
    work.textContent = '';
    const head = el('div', 'work-head');
    head.appendChild(el('h2', 'work-title', 'Preview'));
    const shut = el('button', 'linky', 'Close');
    shut.type = 'button';
    shut.onclick = closeAsk;
    head.appendChild(shut);
    const body = el('div', 'work-body');
    work.append(head, body, status);
    showPaper(body, 'lineup', shown);
  };

  const saveBtn = el('button', 'solid', 'Save version');
  saveBtn.type = 'button';
  saveBtn.onclick = async () => {
    saveBtn.disabled = true;
    try {
      const got = await ask(`/api/spaces/${space.id}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner: owner(),
          titles: lineup(),
          groups: shown ? shown.clusters.length : null,
          sizes: shown ? shown.clusters.map((c) => c.length) : [],
        }),
      });
      const had = space.versions.length;
      space = got;
      drawVersions();
      status.textContent = space.versions.length > had
        ? 'Saved'
        : 'Nothing has changed since your last version.';
    } catch (e) {
      status.textContent = e.message || 'That version could not be saved.';
    } finally {
      saveBtn.disabled = false;
    }
  };
  end.append(resetBtn, printBtn, saveBtn);

  const desk = el('div', 'desk');
  rail = el('aside', 'desk-rail');
  work = el('section', 'work');
  desk.append(rail, work);
  stage.appendChild(desk);

  status = el('p', 'work-status');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');

  rail.appendChild(el('p', 'desk-rail-head', 'The lineup'));
  chipBox = el('div', 'chips');
  rail.appendChild(chipBox);

  const addField = el('input');
  addField.type = 'text';
  addField.placeholder = 'Add a title';
  addField.onkeydown = async (ev) => {
    if (ev.key !== 'Enter') return;
    const t = addField.value.trim();
    if (!t) return;
    if (space.titles.some((x) => x.toLowerCase() === t.toLowerCase())) {
      status.textContent = `${t} is already in the lineup.`;
      return;
    }
    addField.value = '';
    await save({ titles: space.titles.concat(t) });
    drawChips();
    runSpace();
  };
  rail.appendChild(addField);

  rail.appendChild(el('p', 'desk-rail-what desk-rail-slots',
    'Number of slots'));
  slotField = el('input');
  slotField.type = 'number';
  slotField.min = '1';
  slotField.className = 'narrow';
  slotField.value = String(space.slots);
  slotField.onchange = async () => {
    const n = Math.max(1, Number(slotField.value) || space.slots);
    slotField.value = String(n);
    await save({ slots: n });
    drawCounts();
  };
  rail.appendChild(slotField);

  rail.appendChild(el('p', 'desk-rail-head desk-rail-gap', 'Ask Slate'));
  ASKS.forEach(([key, label]) => {
    const btn = el('button', 'ask', label);
    btn.type = 'button';
    btn.dataset.ask = key;
    btn.onclick = () => (openAsk === key ? closeAsk() : showAsk(key));
    rail.appendChild(btn);
  });

  rail.appendChild(el('p', 'desk-rail-head desk-rail-gap', 'Versions'));
  versionBox = el('div', 'desk-versions');
  rail.appendChild(versionBox);

  const keepPick = el('select');
  keepPick.className = 'narrow';
  drawSpace.keepPick = keepPick;
  drawSpace.drawKeep = () => {
    const n = lineup().length;
    const was = keepPick.value;
    keepPick.textContent = '';
    for (let k = n - 1; k >= 4; k -= 1) {
      keepPick.appendChild(el('option', null, String(k)));
    }
    if (was && Number(was) < n) keepPick.value = was;
  };

  drawChips();
  drawSpace.drawKeep();
  drawVersions();
  drawCounts();
}

function markAsk() {
  rail.querySelectorAll('.ask').forEach((b) => {
    b.classList.toggle('on', b.dataset.ask === openAsk);
  });
}

function closeAsk() {
  openAsk = null;
  markAsk();
  showFigure();
}

function showAsk(key) {
  openAsk = key;
  markAsk();
  work.textContent = '';
  const head = el('div', 'work-head');
  head.appendChild(el('h2', 'work-title',
    ASKS.find(([k]) => k === key)[1]));
  const shut = el('button', 'linky', 'Close');
  shut.type = 'button';
  shut.onclick = closeAsk;
  head.appendChild(shut);
  work.appendChild(head);

  const body = el('div', 'work-body');
  work.append(body, status);

  if (key === 'fewer') fewerAsk(body);
  else if (key === 'swap') swapAsk(body);
  else if (key === 'stand') standAsk(body);
  else compareAsk(body);

  const out = body.querySelector('.out');
  if (out && !out.children.length && shown) {
    out.appendChild(drawn(shown));
    out.classList.add('standing');
  }
}

function showFigure() {
  work.textContent = '';
  figure = el('div', 'work-figure');
  feet = el('div', 'work-feet');
  work.append(figure, feet, status);
  if (shown) paintSpace(shown, new Map());
}

const CHIPS_SHOWN = 5;

function drawChips() {
  chipBox.textContent = '';
  const all = lineup();
  const show = chipsOpen ? all : all.slice(0, CHIPS_SHOWN);
  const lost = new Set((shown && shown.unresolved) || []);
  show.forEach((t) => {
    const chip = el('button', lost.has(t) ? 'chip lost' : 'chip');
    chip.type = 'button';
    if (lost.has(t)) chip.title = `Qloo could not place ${t}`;
    chip.appendChild(document.createTextNode(t));
    chip.appendChild(el('span', 'chip-x', '\u00d7'));
    chip.onclick = async () => {
      await save({ titles: all.filter((x) => x !== t) });
      drawChips();
      drawSpace.drawKeep();
      runSpace();
    };
    chipBox.appendChild(chip);
  });
  if (!chipsOpen && all.length > CHIPS_SHOWN) {
    const more = el('button', 'chips-more',
      `${all.length - CHIPS_SHOWN} more`);
    more.type = 'button';
    more.onclick = () => { chipsOpen = true; drawChips(); };
    chipBox.appendChild(more);
  }
}

function drawCounts() {
  const n = lineup().length;
  const noun = nounFor(space.entity_type, n);
  const groups = shown ? `${shown.clusters.length} groups` : '';
  const over = n - space.slots;
  const gap = over > 0 ? `${over} slots over`
    : over < 0 ? `${-over} slots free` : '';
  const counts = document.querySelector('.deskbar-counts');
  if (!counts) return;
  counts.textContent = [`${n} ${noun}`, groups, gap].filter(Boolean)
    .join(' \u00b7 ');
  counts.classList.toggle('over', over > 0);

  const back = document.querySelector('.deskbar-end .ghost');
  if (back && started) {
    const here2 = lineup();
    back.hidden = started.length === here2.length
      && started.every((t, i) => t === here2[i]);
  }
}

function waiting(on) {
  if (!figure) return;
  figure.classList.toggle('thinking', on && !!shown);
  if (on && !shown) {
    figure.textContent = '';
    const bones = el('div', 'bones');
    for (let i = 0; i < 3; i += 1) {
      const col = el('div', 'bone-col');
      for (let j = 0; j < 3 + i; j += 1) col.appendChild(el('span'));
      bones.appendChild(col);
    }
    figure.appendChild(bones);
  }
}

async function runSpace(opts) {
  if (openAsk) closeAsk();
  if (!figure) showFigure();
  const mine = ++asked;
  status.textContent = 'Working it out';
  waiting(true);
  try {
    const d = await askPanelApi({});
    if (mine !== asked) return;
    waiting(false);
    if (!d.films || d.films.length < 2) { tooThin(d); return; }
    const before = seatOf(figure);
    paintSpace(d, before);
    drawChips();
    drawCounts();
    if ((d.unresolved || []).length) {
      status.textContent = `Qloo could not place `
        + `${nameList(d.unresolved)}.`;
      return;
    }
    status.textContent = '';
  } catch (e) {
    if (mine !== asked) return;
    waiting(false);
    figure.textContent = '';
    failure(e, figure, () => runSpace(opts));
  }
}

const seatOf = (node) => {
  const at = new Map();
  if (!node) return at;
  node.querySelectorAll('.film[data-title]').forEach((row) => {
    at.set(row.dataset.title, row.getBoundingClientRect());
  });
  return at;
};

const askPanelApi = (extra) => ask('/api/panel', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    films: lineup(),
    entity_type: space.entity_type,
    drop: [],
    add: [],
    ...extra,
  }),
});

function tooThin(d) {
  figure.textContent = '';
  const said = el('div', 'nothing');
  said.appendChild(el('p', 'nothing-head',
    'There is not enough here to separate.'));
  said.appendChild(el('p', 'nothing-why',
    `Slate placed ${(d.films || []).length} of your ${lineup().length} `
    + 'titles against Qloo. It needs at least four it can read before '
    + 'groups mean anything.'));
  if ((d.unresolved || []).length) {
    said.appendChild(el('p', 'nothing-why',
      `It could not place ${nameList(d.unresolved)}.`));
  }
  figure.appendChild(said);
  status.textContent = 'Too few titles could be placed';
  shown = null;
  drawCounts();
}

let earlier = null;
let showingEarlier = false;

function paintSpace(d, before) {
  if (shown && shown !== d) earlier = shown;
  shown = d;
  showingEarlier = false;
  figure.textContent = '';
  figure.appendChild(drawn(d));
  settleInto(figure, before, (d.diff && d.diff.moved) || []);
  drawFeet();
}

function drawFeet() {
  if (!feet) return;
  feet.textContent = '';
  if (!earlier) return;
  const flip = el('button', 'ghost',
    showingEarlier ? 'View current shape' : 'View previous shape');
  flip.type = 'button';
  flip.onclick = () => {
    showingEarlier = !showingEarlier;
    figure.textContent = '';
    if (showingEarlier) {
      figure.appendChild(el('p', 'figure-when', 'Before your last change'));
    }
    figure.appendChild(drawn(showingEarlier ? earlier : shown));
    drawFeet();
  };
  feet.appendChild(flip);
}

function drawn(d) {
  const sec = chapter(d, null);
  sec.classList.add('shown');
  ['.chapter-title', '.verdict-line'].forEach((sel) => {
    const gone = sec.querySelector(sel);
    if (gone) gone.remove();
  });
  return sec;
}

function fewerAsk(body) {
  const row = el('div', 'work-form');
  row.appendChild(el('span', 'fine', 'Keep'));
  const pick = drawSpace.keepPick;
  drawSpace.drawKeep();
  row.appendChild(pick);
  row.appendChild(el('span', 'fine', `of the ${lineup().length}`));
  const go = el('button', 'solid', 'Find the best set');
  go.type = 'button';
  row.appendChild(go);
  body.appendChild(row);

  const out = el('div', 'out');
  body.appendChild(out);

  go.onclick = async () => {
    go.disabled = true;
    go.textContent = 'Working it out';
    out.textContent = '';
    out.classList.remove('standing');
    try {
      const d = await askPanelApi({ keep: Number(pick.value) });
      out.textContent = '';
      out.appendChild(drawn(d));

      const split = el('div', 'work-split');
      const left = el('div');
      if (d.chance) {
        const c = d.chance;
        block(left, 'Against the sets you could have picked', c.beats
          ? `Of the ${c.possible.toLocaleString()} possible sets of `
            + `${d.films.length} from your ${lineup().length}, this one keeps `
            + 'its two most alike titles further apart than '
            + `${c.beats.toLocaleString()} of them.`
          : `No set of ${d.films.length} from your ${lineup().length} keeps `
            + 'its two most alike titles further apart than this one.');
      }
      const take = el('button', 'solid', 'Keep this set');
      take.type = 'button';
      take.onclick = async () => {
        await save({ titles: d.films.map((f) => f.title) });
        closeAsk();
        drawChips();
        drawSpace.drawKeep();
        runSpace();
        status.textContent = 'That set is now the lineup.';
      };
      const acts = el('div', 'row');
      acts.appendChild(take);
      left.appendChild(acts);

      const side = el('div', 'aside-card');
      side.appendChild(el('p', 'aside-head', 'What it cost'));
      const was = shown ? shown.clusters.length : null;
      side.appendChild(el('p', 'aside-line', was
        ? `${was} groups become ${d.clusters.length}.`
        : `${d.clusters.length} groups.`));
      const gone = (d.dropped || []);
      if (gone.length) {
        const p2 = el('p', 'aside-line dim');
        withTitles(p2, `Slate dropped ${nameList(gone)}.`,
          lineup().concat(gone));
        side.appendChild(p2);
      }
      split.append(left, side);
      out.appendChild(split);
      status.textContent = '';
    } catch (e) {
      failure(e, out, () => go.onclick());
    } finally {
      go.disabled = false;
      go.textContent = 'Find the best set';
    }
  };
}

function swapAsk(body) {
  body.appendChild(el('p', 'work-lede',
    'Slate takes a slot the lineup can spare, asks Qloo for titles unlike '
    + 'what you have, and tests each one by rebuilding the whole lineup. It '
    + 'keeps a change only if the result improves.'));

  const row = el('div', 'work-form');
  const go = el('button', 'solid', 'Look for one');
  go.type = 'button';
  row.appendChild(go);
  body.appendChild(row);

  const out = el('div', 'out');
  body.appendChild(out);

  go.onclick = async () => {
    go.disabled = true;
    go.textContent = 'Testing candidates';
    out.textContent = '';
    out.classList.remove('standing');
    try {
      const d = await askPanelApi({ swap: true });
      out.textContent = '';
      paintSwap(out, d);
      status.textContent = '';
    } catch (e) {
      failure(e, out, () => go.onclick());
    } finally {
      go.disabled = false;
      go.textContent = 'Look for one';
    }
  };
}

function paintSwap(out, d) {
  const a = d.agent || {};
  const swap = (a.swaps || [])[0];
  const names = lineup().concat((a.rejected || []).map((r) => r.film),
    swap ? [swap.in, swap.out] : []);

  if (swap) {
    const head = el('p', 'work-swap');
    head.appendChild(el('span', 'work-swap-out', swap.out));
    head.appendChild(el('span', 'work-swap-arrow', '\u2192'));
    head.appendChild(el('span', 'work-swap-in', swap.in));
    out.appendChild(head);
  }

  out.appendChild(drawn(d));

  const split = el('div', 'work-split');
  const left = el('div');

  if (swap) {
    block(left, 'What the swap does', a.verdict || '');
    const take = el('button', 'solid', 'Make this swap');
    take.type = 'button';
    take.onclick = async () => {
      await save({ titles: d.films.map((f) => f.title) });
      closeAsk();
      drawChips();
      drawSpace.drawKeep();
      runSpace();
      status.textContent = 'The swap was made.';
    };
    const acts = el('div', 'row');
    acts.appendChild(take);
    left.appendChild(acts);
  } else {
    const wrap = el('div', 'said');
    wrap.appendChild(el('p', 'work-nothing', 'Nothing was changed.'));
    const why = el('p', 'said-line');
    withTitles(why, a.verdict
      || 'Every candidate was tested and none improved the lineup.', names);
    wrap.appendChild(why);
    left.appendChild(wrap);
  }

  if ((a.rejected || []).length) {
    const side = el('div', 'aside-card');
    side.appendChild(el('p', 'aside-head',
      swap ? 'Also tested' : 'Tested and turned down'));
    a.rejected.slice(0, 5).forEach((r) => {
      const p2 = el('p', 'aside-line');
      p2.appendChild(el('span', 'aside-name', r.film));
      withTitles(p2, ` \u2014 ${r.why}`, names);
      side.appendChild(p2);
    });
    side.appendChild(el('p', 'aside-note',
      'Each candidate was added and the groups worked out again from '
      + 'scratch. A change is kept only if the result improves.'));
    split.append(left, side);
  } else {
    split.appendChild(left);
  }
  out.appendChild(split);
}

function drawVersions() {
  versionBox.textContent = '';
  const kept = space.versions || [];
  if (!kept.length) {
    versionBox.appendChild(el('p', 'fine', 'Nothing saved yet.'));
    return;
  }
  const when = (at) => new Date(at * 1000).toLocaleString('en-GB',
    { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

  const top = el('div', 'version');
  top.appendChild(el('span', 'version-when', when(kept[0].at)));
  const open = el('button', 'linky', 'Open');
  open.type = 'button';
  open.onclick = () => previewVersion(kept[0]);
  top.appendChild(open);
  versionBox.appendChild(top);

  if (kept.length > 1) {
    const all = el('button', 'linky', 'All versions');
    all.type = 'button';
    all.onclick = () => allVersions(kept);
    versionBox.appendChild(all);
  }
  versionBox.appendChild(el('p', 'fine', 'Keeps your last twenty.'));
}

function shut(sheet) {
  sheet.remove();
  document.body.classList.remove('held');
}

async function previewVersion(v) {
  openAsk = 'version';
  markAsk();
  work.textContent = '';

  const head = el('div', 'work-head');
  const when = new Date(v.at * 1000).toLocaleString('en-GB',
    { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  head.appendChild(el('h2', 'work-title', `Saved ${when}`));
  const shut = el('button', 'linky', 'Close');
  shut.type = 'button';
  shut.onclick = closeAsk;
  head.appendChild(shut);
  work.appendChild(head);

  const body = el('div', 'work-body');
  work.append(body, status);
  body.appendChild(el('p', 'work-lede', 'Working it out'));

  try {
    const d = await ask('/api/panel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        films: v.titles, entity_type: space.entity_type, drop: [], add: [],
      }),
    });
    body.textContent = '';
    body.appendChild(drawn(d));
    const acts = el('div', 'row');
    const apply = el('button', 'solid', 'Use this version');
    apply.type = 'button';
    apply.onclick = async () => {
      await save({ titles: v.titles });
      closeAsk();
      drawChips();
      drawSpace.drawKeep();
      runSpace();
      status.textContent = 'That version is now the lineup.';
    };
    acts.appendChild(apply);
    body.appendChild(acts);
  } catch (e) {
    body.textContent = '';
    failure(e, body, () => previewVersion(v));
  }
}

function allVersions(kept) {
  openAsk = 'versions';
  markAsk();
  work.textContent = '';

  const head = el('div', 'work-head');
  head.appendChild(el('h2', 'work-title', 'Versions'));
  const shut = el('button', 'linky', 'Close');
  shut.type = 'button';
  shut.onclick = closeAsk;
  head.appendChild(shut);
  work.appendChild(head);

  const body = el('div', 'work-body');
  work.append(body, status);

  const when = (at) => new Date(at * 1000).toLocaleString('en-GB',
    { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  kept.forEach((v) => {
    const row = el('div', 'version-row');
    row.appendChild(el('span', 'version-when', when(v.at)));
    row.appendChild(el('span', 'version-what',
      `${v.titles.length} ${nounFor(space.entity_type, v.titles.length)}`
      + (v.groups ? ` \u00b7 ${v.groups} groups` : '')));
    const open = el('button', 'ghost', 'Open');
    open.type = 'button';
    open.onclick = () => previewVersion(v);
    row.appendChild(open);
    body.appendChild(row);
  });
  body.appendChild(el('p', 'aside-note', 'Keeps your last twenty.'));
}

function block(node, head, fill) {
  const wrap = el('div', 'said');
  wrap.appendChild(el('p', 'said-head', head));
  const row = el('p', 'said-line');
  if (typeof fill === 'string') withTitles(row, fill, namePool());
  else row.appendChild(fill);
  wrap.appendChild(row);
  node.appendChild(wrap);
}

let extraNames = [];
const namePool = () => lineup().concat(extraNames);

function standAsk(body) {
  const row = el('div', 'work-form');
  const field = el('input');
  field.type = 'text';
  field.placeholder = `A ${nounFor(space.entity_type, 1)} you are weighing up`;
  const go = el('button', 'solid', 'Analyse');
  go.type = 'button';
  const egg = el('button', 'linky', 'Use an example');
  egg.type = 'button';
  row.append(field, go, egg);
  body.appendChild(row);

  const out = el('div', 'out');
  body.appendChild(out);

  egg.onclick = async () => {
    try {
      const got = await ask(`/api/candidates?kind=${space.entity_type}`);
      const pick = (got.one || []).filter((t) => !lineup().includes(t));
      if (pick.length) {
        field.value = pick[Math.floor(Math.random() * pick.length)];
      }
    } catch {  }
  };

  field.onkeydown = (ev) => { if (ev.key === 'Enter') go.onclick(); };

  go.onclick = async () => {
    const want = field.value.trim();
    if (!want) return;
    go.disabled = true;
    go.textContent = 'Working it out';
    out.textContent = '';
    out.classList.remove('standing');
    try {
      const b = await ask('/api/brief', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lineup: lineup(),
          candidate: want,
          entity_type: space.entity_type,
          slots: space.slots,
        }),
      });
      extraNames = [b.candidate.film];
      paintStand(out, b);
      status.textContent = '';
    } catch (e) {
      failure(e, out, () => go.onclick());
    } finally {
      go.disabled = false;
      go.textContent = 'Analyse';
    }
  };
}

function paintStand(out, b) {
  out.textContent = '';
  const sheetSpot = el('div', 'paper-spot');
  const name = b.candidate.film;
  out.appendChild(drawn(b.shape));

  const split = el('div', 'work-split');
  const left = el('div');

  block(left, 'Changes to the lineup',
    b.groups_after === b.groups_before
      ? (b.regrouped && b.regrouped.length
        ? `The number of groups stays at ${b.groups_before}, but the titles `
          + 'regroup around it.'
        : `The number of groups stays at ${b.groups_before}.`)
      : b.groups_after < b.groups_before
        ? `The number of groups falls from ${b.groups_before} to `
          + `${b.groups_after}. It sits between groups that were separate `
          + 'before, closely enough that they merge.'
        : `The number of groups goes from ${b.groups_before} to `
          + `${b.groups_after}.`);

  if (b.role === 'bridge') {
    const joins = (b.connects || []).map(letterFor);
    block(left, 'Its part in the lineup',
      `${name} is a bridge. It connects `
      + (joins.length === 2
        ? `group ${joins[0]} and group ${joins[1]}.`
        : `groups ${joins.slice(0, -1).join(', ')} and `
          + `${joins[joins.length - 1]}.`));
  } else if (b.role === 'alone') {
    block(left, 'Its part in the lineup',
      `${name} is an outlier. It sits further from the rest than anything `
      + 'else here.');
  }

  if (b.over > 0 && b.spare) {
    const [x, y] = b.spare.films;
    block(left, 'What it could replace',
      `${x} or ${y} costs least to drop. They are the two most alike titles `
      + 'in the lineup, so whichever stays still covers that ground.');
  }

  const acts = el('div', 'row');
  const take = el('button', 'solid', 'Add it to the lineup');
  take.type = 'button';
  take.onclick = async () => {
    await save({ titles: lineup().concat(name) });
    closeAsk();
    drawChips();
    drawSpace.drawKeep();
    runSpace();
  };
  const show = el('button', 'ghost', 'See the brief');
  show.type = 'button';
  show.onclick = () => showPaper(sheetSpot, 'stand', b);
  acts.append(take, show);
  left.appendChild(acts);

  split.append(left, distanceCard(b.candidate.distances));
  out.append(split, sheetSpot);
}

function distanceCard(rows) {
  const side = el('div', 'aside-card');
  side.appendChild(el('p', 'aside-head', 'How far it sits from each'));
  const table = el('table', 'aside-table');
  const show = (n) => {
    table.textContent = '';
    rows.slice(0, n).forEach((x) => {
      const tr = el('tr');
      const td = el('td');
      withTitles(td, x.film, namePool());
      tr.append(td, el('td', 'd', x.distance.toFixed(1)));
      table.appendChild(tr);
    });
    if (n < rows.length) {
      const tr = el('tr');
      const more = el('button', 'linky', `+${rows.length - n} more`);
      more.type = 'button';
      more.onclick = () => show(rows.length);
      const td = el('td');
      td.appendChild(more);
      tr.append(td, el('td'));
      table.appendChild(tr);
    }
  };
  show(4);
  side.appendChild(table);
  side.appendChild(el('p', 'aside-note',
    'Distance measures shared taste. It does not say why two titles are '
    + 'close.'));
  return side;
}

function compareAsk(body) {
  const form = el('div', 'work-form compare-form');

  const col = el('div');
  col.appendChild(el('p', 'fine',
    'The titles you are choosing between, one per line'));
  const area = el('textarea');
  area.rows = 4;
  area.spellcheck = false;
  col.appendChild(area);
  form.appendChild(col);

  const slotCol = el('div');
  slotCol.appendChild(el('p', 'fine', 'Room for'));
  const slots = el('select');
  slots.className = 'narrow';
  [1, 2, 3].forEach((n) => slots.appendChild(el('option', null, String(n))));
  slots.value = '2';
  slotCol.appendChild(slots);
  form.appendChild(slotCol);

  const go = el('button', 'solid', 'Analyse');
  go.type = 'button';
  const egg = el('button', 'linky', 'Use an example');
  egg.type = 'button';
  form.append(go, egg);
  body.appendChild(form);

  const out = el('div', 'out');
  body.appendChild(out);

  egg.onclick = async () => {
    try {
      const got = await ask(`/api/candidates?kind=${space.entity_type}`);
      const many = (got.many || []).filter((t) => !lineup().includes(t));
      if (many.length) area.value = many.join('\n');
    } catch {  }
  };

  go.onclick = async () => {
    const candidates = area.value.split('\n')
      .map((t) => t.trim()).filter(Boolean);
    if (!candidates.length) return;
    go.disabled = true;
    go.textContent = 'Working it out';
    out.textContent = '';
    out.classList.remove('standing');
    try {
      const got = await ask('/api/choose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lineup: lineup(),
          candidates,
          slots: Number(slots.value),
          entity_type: space.entity_type,
        }),
      });
      extraNames = candidates;
      paintChoose(out, got);
      status.textContent = '';
    } catch (e) {
      failure(e, out, () => go.onclick());
    } finally {
      go.disabled = false;
      go.textContent = 'Analyse';
    }
  };
}

function paintChoose(out, got) {
  out.textContent = '';
  const sheetSpot = el('div', 'paper-spot');
  const best = got.best;
  out.appendChild(drawn(got.shape));

  const split = el('div', 'work-split');
  const left = el('div');

  const wrap = el('div', 'said');
  wrap.appendChild(el('p', 'said-head', 'Which to take'));
  const names = el('p', 'work-answer');
  withTitles(names, `${nameList(best.films)}.`, namePool());
  wrap.appendChild(names);

  const said = {};
  best.films.forEach((t) => {
    const fresh = (best.clusters[best.joins[t]] || []).length === 1;
    const key = best.roles[t] === 'bridge' ? 'bridge' : fresh ? 'new' : 'joins';
    (said[key] = said[key] || []).push(t);
  });
  if (said.new) {
    wrap.appendChild(line(`${nameList(said.new)} `
      + `${said.new.length > 1 ? 'each reach a group' : 'reaches a group'} `
      + 'the lineup did not have.'));
  }
  if (said.bridge) {
    wrap.appendChild(line(`${nameList(said.bridge)} `
      + `${said.bridge.length > 1 ? 'connect' : 'connects'} groups that `
      + 'nothing else joins.'));
  }
  if (said.joins) {
    const many = said.joins.length > 1;
    wrap.appendChild(line(`${nameList(said.joins)} `
      + `${many ? 'join groups' : 'joins a group'} the lineup already had, `
      + `but ${many ? 'sit' : 'sits'} further from `
      + `${many ? 'them' : 'it'} than the others would.`));
  }
  if (!said.new && !said.bridge && !said.joins) {
    wrap.appendChild(line('None of the titles you gave reaches a group the '
      + 'lineup did not have. These sit furthest from what is already '
      + 'there.'));
  }
  left.appendChild(wrap);

  if (got.next) {
    block(left, 'The next best set',
      `${nameList(got.next.films)}. Their two most alike titles sit closer `
      + 'together than in the set above.');
  }

  if ((got.unplaced || []).length) {
    block(left, 'Could not be placed',
      `${nameList(got.unplaced)}. Qloo has too little on `
      + `${got.unplaced.length > 1 ? 'them' : 'it'} to say where `
      + `${got.unplaced.length > 1 ? 'they sit' : 'it sits'} against your `
      + 'lineup.');
  }

  const acts = el('div', 'row');
  const take = el('button', 'solid', 'Add them to the lineup');
  take.type = 'button';
  take.onclick = async () => {
    await save({ titles: lineup().concat(best.films) });
    closeAsk();
    drawChips();
    drawSpace.drawKeep();
    runSpace();
  };
  const show = el('button', 'ghost', 'See the brief');
  show.type = 'button';
  show.onclick = () => showPaper(sheetSpot, 'choose', got);
  acts.append(take, show);
  left.appendChild(acts);

  const side = el('div', 'aside-card');
  side.appendChild(el('p', 'aside-head', 'Every set, best first'));
  const table = el('table', 'aside-table');
  const head = el('tr', 'head');
  ['Set', 'Groups', 'Closest'].forEach((t) => {
    head.appendChild(el('td', null, t));
  });
  table.appendChild(head);
  got.every.slice(0, 5).forEach((r, i) => {
    const tr = el('tr', i ? null : 'win');
    const td = el('td');
    withTitles(td, r.films.join(' + '), namePool());
    tr.append(td, el('td', 'd', String(r.groups)),
      el('td', 'd', r.closest.toFixed(1)));
    table.appendChild(tr);
  });
  if (got.every.length > 5) {
    const tr = el('tr');
    tr.appendChild(el('td', 'fine', `+${got.every.length - 5} more`));
    table.appendChild(tr);
  }
  side.appendChild(table);
  side.appendChild(el('p', 'aside-note',
    'Each set was added and the groups worked out again. Ranked by how far '
    + 'apart their two most alike titles end up.'));

  split.append(left, side);
  out.append(split, sheetSpot);
}

function line(text) {
  const p = el('p', 'said-line');
  withTitles(p, text, namePool());
  return p;
}

async function paperFor(kind, data) {
  const body = JSON.stringify({
    kind,
    name: space.name,
    slots: space.slots,
    data,
  });
  const res = await fetch('/api/paper', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  });
  if (!res.ok) throw new Error('That document could not be made.');
  return { markup: await res.text(), body };
}

function showPaper(node, kind, data) {
  node.textContent = '';
  const wrap = el('div', 'paper');
  const head = el('div', 'paper-head');
  head.appendChild(el('p', 'aside-head', 'The brief'));
  const acts = el('div', 'paper-acts');
  head.appendChild(acts);
  wrap.appendChild(head);

  const frame = document.createElement('iframe');
  frame.className = 'paper-frame';
  frame.title = 'The brief as it will print';
  wrap.appendChild(frame);
  node.appendChild(wrap);

  const said = el('p', 'aside-note');
  wrap.appendChild(said);

  paperFor(kind, data).then(({ markup, body }) => {
    frame.srcdoc = markup;

    const get = el('button', 'solid', 'Download PDF');
    get.type = 'button';
    get.onclick = async () => {
      get.disabled = true;
      said.textContent = '';
      try {
        const res = await fetch('/api/paper.pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body,
        });
        if (res.status === 501) {
          said.textContent = 'This server cannot make a file. Printing gives '
            + 'the same document.';
          get.textContent = 'Print';
          get.onclick = () => {
            const win = frame.contentWindow;
            if (!win) return;
            win.focus();
            win.print();
          };
          return;
        }
        if (!res.ok) throw new Error('That did not work.');
        const blob = await res.blob();
        const link = el('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${space.name}.pdf`;
        link.click();
        URL.revokeObjectURL(link.href);
      } catch (e) {
        said.textContent = e.message || 'That did not work.';
      } finally {
        get.disabled = false;
      }
    };
    acts.appendChild(get);
  }).catch((e) => {
    said.textContent = e.message || 'That document could not be made.';
  });
}

window.addEventListener('hashchange', () => {
  const id = window.location.hash.slice(1);
  if (id) openSpace(id);
  else load();
});

const opening = window.location.hash.slice(1);
if (opening) openSpace(opening);
else load();
