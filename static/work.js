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
    let body = null;
    try {
      body = await res.json();
      why = body.detail || body.error || why;
    } catch {  }
    const err = new Error(why);
    err.status = res.status;
    err.body = body;
    throw err;
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
  bar: [3, 2, 2],
  groups: [
    { letter: 'A', n: 3,
      films: [['Anatomy of a Fall'], ['The Zone of Interest'], ['Club Zero']] },
    { letter: 'B', n: 2, films: [['Perfect Days'], ['Past Lives']] },
    { letter: 'C', n: 2,
      films: [['Youth'], ['Monster', 'outlier', 'alone']] },
  ],
  bridges: [['Fallen Leaves', '2023', 'B\u00b7C']],
};

const SAMPLE_TITLES = ['Monster', 'Anatomy of a Fall', 'Past Lives',
  'Fallen Leaves', 'Club Zero', 'Youth', 'The Zone of Interest',
  'Perfect Days'];

function mixedPanel(info, titles, onPick) {
  const fig = el('div', 'taste');
  fig.appendChild(el('p', 'mixed-lede',
    `These titles span ${spellSmall(info.kinds.length)} kinds.`));
  fig.appendChild(el('p', 'mixed-why',
    'Slate creates one workspace per kind of title, so picking one leaves '
    + 'the others out.'));

  const cols = el('div', 'mixed-cols');
  const blocks = info.kinds.slice();
  if ((info.missing || []).length) {
    blocks.push({ label: 'Not recognised', titles: info.missing,
                  enough: false, lost: true });
  }
  blocks.forEach((kind) => {
    const col = el('div');
    col.appendChild(el('p', 'mixed-head', kind.lost
      ? `${kind.label} \u00b7 ${kind.titles.length}`
      : `Matched as ${kind.label} \u00b7 ${kind.titles.length}`));
    kind.titles.forEach((t) => {
      const row = el('p', 'taste-film');
      row.appendChild(document.createTextNode(t.title || t));
      if (t.year) row.appendChild(el('span', 'year', String(t.year)));
      col.appendChild(row);
    });
    if (kind.enough) {
      const go = el('button', 'mixed-use', `Use these ${kind.titles.length}`);
      go.type = 'button';
      go.onclick = () => onPick(kind);
      col.appendChild(go);
    } else if (!kind.lost) {
      col.appendChild(el('p', 'mixed-short', `Needs ${info.least}.`));
    }
    cols.appendChild(col);
  });
  fig.appendChild(cols);
  return fig;
}

const SMALL = ['no', 'one', 'two', 'three', 'four', 'five', 'six'];
const spellSmall = (n) => SMALL[n] || String(n);
const Caps = (t) => t.charAt(0).toUpperCase() + t.slice(1);

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

  const band = el('div', 'taste-links');
  band.appendChild(el('p', 'taste-links-head', 'Bridges'));
  SAMPLE.bridges.forEach(([title, year, spans]) => {
    const one = el('div', 'taste-link');
    const name = el('p', 'taste-film');
    name.appendChild(document.createTextNode(title));
    name.appendChild(el('span', 'taste-year', year));
    one.appendChild(name);
    one.appendChild(el('span', 'taste-tag bridge', spans));
    band.appendChild(one);
  });
  fig.appendChild(band);
  return fig;
}

function draw() {
  here.textContent = '';
  end.textContent = '';
  stage.textContent = '';

  const bar = document.querySelector('.deskbar');
  if (bar) {
    bar.hidden = false;
    bar.classList.add('bare');
  }

  const top = el('div', 'door');
  top.appendChild(el('h1', 'door-title', 'Start with a lineup.'));
  top.appendChild(el('p', 'door-lede',
    'Four to twenty-four titles, one per line. Films, music, books, '
    + 'podcasts or TV shows. In case a name exists in more than one type, '
    + 'adding a year in brackets, like Monster (2023), helps Slate find the '
    + 'one you mean.'));

  const pair = el('div', 'door-pair');

  const left = el('div', 'door-ask');
  const area = el('textarea');
  area.spellcheck = false;
  area.placeholder = SAMPLE_TITLES.join('\n');
  left.appendChild(area);

  const row = el('div', 'row');
  const make = el('button', 'solid', 'Analyse this lineup');
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

  pair.append(left, right);
  top.appendChild(pair);
  stage.appendChild(top);

  make.onclick = async () => {
    const titles = area.value.split('\n').map((t) => t.trim()).filter(Boolean);
    const refuse = (why) => {
      said.classList.add('refused');
      said.textContent = why;
    };
    said.classList.remove('refused');
    if (titles.length < 4) {
      refuse('Four titles at least, so there is something to separate.');
      return;
    }
    if (titles.length > 24) {
      refuse('Twenty-four titles at most.');
      return;
    }
    make.classList.add('busy');
    make.textContent = 'Working it out';
    said.textContent = `Asking Qloo about ${titles.length} titles.`;
    try {
      const made = await ask('/api/spaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner: owner(), titles,
          entity_type: area.dataset.entityType || undefined,
        }),
      });
      window.location.href = `/app#${made.id}`;
      window.location.reload();
    } catch (e) {
      const mix = e && e.body && e.body.mixed ? e.body : null;
      if (mix) {
        said.textContent = '';
        right.textContent = '';
        right.appendChild(mixedPanel(mix, titles, (kind) => {
          area.value = kind.titles
            .map((t) => (t.title || t)).join('\n');
          area.dataset.entityType = kind.entity_type;
          make.onclick();
        }));
        right.appendChild(el('p', 'door-caption',
          'What Slate found in your list'));
      } else {
        refuse(e.message || 'That did not work.');
      }
    } finally {
      make.classList.remove('busy');
      make.textContent = 'Analyse this lineup';
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

  const band = el('div', 'door-band');
  const inner = el('div', 'door-band-in');
  inner.appendChild(el('p', 'door-head', 'Earlier workspaces'));
  if (spaces.length) {
    const cards = el('div', 'door-cards');
    spaces.forEach((w) => cards.appendChild(spaceRow(w)));
    inner.appendChild(cards);
  } else {
    inner.appendChild(el('p', 'door-none',
      'Nothing yet. Analyse a lineup and it will be kept here.'));
  }
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
  const n = (typeof w.placed === 'number' && w.placed > 0)
    ? w.placed : w.titles.length;
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
    if (!await confirmDelete(w.name)) return;
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

function fold(shown, total, draw) {
  let open = false;
  const btn = el('button', 'fold');
  btn.type = 'button';
  const paint = () => {
    btn.textContent = open ? 'Show fewer' : `+${total - shown} more`;
    draw(open ? total : shown);
  };
  btn.onclick = () => { open = !open; paint(); };
  paint();
  return total > shown ? btn : null;
}

function noted(out, err, fallback) {
  const code = err && err.status;
  if (code === 404 || code === 409 || code === 422) {
    out.textContent = '';
    out.appendChild(el('p', 'work-note', (err && err.message) || ''));
    if (shown) {
      out.appendChild(el('p', 'out-when', 'The lineup as it stands'));
      out.appendChild(drawn(shown));
    }
    return true;
  }
  fallback();
  return false;
}

function said(text) {
  if (said.show) said.show(text);
}

const inGroup = (g) => (Array.isArray(g) ? g : (g && g.films) || []);

async function openSpace(id) {
  const bar = document.querySelector('.deskbar');
  if (bar) {
    bar.hidden = false;
    bar.classList.remove('bare');
  }
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
  ['fewer', 'Fit it into fewer slots', 'Keep the strongest smaller set'],
  ['swap', 'Find a title that adds a new group',
    'Reach an audience the lineup misses'],
  ['stand', 'Check a new title against the lineup',
    'See what changes if it is added'],
  ['compare', 'Compare titles before adding',
    'Choose between candidates'],
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
    const last = (space.versions || [])[0];
    const to = last ? last.titles : started;
    await save({ titles: to.slice() });
    drawChips();
    drawSpace.drawKeep();
    runSpace();
    status.textContent = last
      ? `Back to your version from ${new Date(last.at * 1000)
        .toLocaleString('en-GB',
          { day: 'numeric', month: 'short', hour: '2-digit',
            minute: '2-digit' })}.`
      : 'Back to the lineup you started with.';
  };

  const printBtn = el('button', 'ghost', 'Preview');
  printBtn.type = 'button';
  printBtn.onclick = () => {
    if (!shown) { status.textContent = 'Nothing to show yet.'; return; }
    showPaper('lineup', shown);
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
          sizes: shown
            ? shown.clusters.map((c) => inGroup(c).length) : [],
        }),
      });
      const had = space.versions.length;
      space = got;
      drawVersions();
      if (space.versions.length > had) {
        said('Saved');
      } else {
        status.textContent = 'Nothing has changed since your last version.';
      }
    } catch (e) {
      status.textContent = e.message || 'That version could not be saved.';
    } finally {
      saveBtn.disabled = false;
    }
  };
  end.append(resetBtn, printBtn, saveBtn);

  const note = el('p', 'deskbar-said');
  note.setAttribute('role', 'status');
  end.appendChild(note);
  said.show = (text) => {
    note.textContent = text;
    note.classList.add('on');
    clearTimeout(said.timer);
    said.timer = setTimeout(() => note.classList.remove('on'), 3000);
  };

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
  ASKS.forEach(([key, label, why]) => {
    const btn = el('button', 'ask');
    btn.type = 'button';
    btn.dataset.ask = key;
    btn.appendChild(el('span', 'ask-what', label));
    btn.appendChild(el('span', 'ask-why', why));
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
    out.appendChild(el('p', 'out-when', 'The lineup as it stands'));
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
  if (all.length > CHIPS_SHOWN) {
    const more = el('button', 'fold', chipsOpen
      ? 'Show fewer' : `+${all.length - CHIPS_SHOWN} more`);
    more.type = 'button';
    more.onclick = () => { chipsOpen = !chipsOpen; drawChips(); };
    chipBox.appendChild(more);
  }
}

function drawCounts() {
  const n = shown ? shown.films.length : lineup().length;
  const noun = nounFor(space.entity_type, n);
  const groups = shown ? `${shown.clusters.length} groups` : '';
  const over = n - space.slots;
  const slot = (n) => `${n} slot${n === 1 ? '' : 's'}`;
  const gap = over > 0 ? `${slot(over)} over`
    : over < 0 ? `${slot(-over)} free` : '';
  const counts = document.querySelector('.deskbar-counts');
  if (!counts) return;
  counts.textContent = '';
  const plain = [`${n} ${noun}`, groups].filter(Boolean).join(' \u00b7 ');
  counts.appendChild(document.createTextNode(plain));
  if (gap) {
    counts.appendChild(document.createTextNode(' \u00b7 '));
    counts.appendChild(el('span', over > 0 ? 'over' : null, gap));
  }

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
    const gone = (d.unresolved || []).concat(d.excluded || []);
    if (space) {
      const fields = {};
      if (gone.length && space.slots === lineup().length) {
        fields.slots = d.films.length;
      }
      if (space.placed !== d.films.length) fields.placed = d.films.length;
      if (Object.keys(fields).length) {
        save(fields).then(() => {
          drawCounts();
          if (slotField) slotField.value = String(space.slots);
        });
      }
    }
    if (gone.length) {
      const note = el('p', 'work-note');
      withTitles(note, `Slate could not place ${nameList(gone)}, so `
        + `${gone.length > 1 ? 'they are' : 'it is'} not in the figure.`,
        lineup());
      figure.insertBefore(note, figure.firstChild);
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
      figure.appendChild(el('p', 'figure-when', 'The lineup before your last change'));
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
        side.appendChild(el('p', 'aside-note',
          'Each dropped title sat closest to one that stayed, so the ground '
          + 'it covered is still covered.'));
      }
      split.append(left, side);
      out.appendChild(split);
      status.textContent = '';
    } catch (e) {
      noted(out, e, () => failure(e, out, () => go.onclick()));
    } finally {
      go.disabled = false;
      go.textContent = 'Find the best set';
    }
  };
}

function swapAsk(body) {
  body.appendChild(el('p', 'work-lede',
    'Every candidate is added to the full lineup and the groups are worked '
    + 'out again from scratch, so nothing is judged on its own. A swap is '
    + 'proposed only if the result is measurably better. If nothing clears '
    + 'that bar, Slate reports no change.'));

  const row = el('div', 'work-form');
  const go = el('button', 'solid', 'Look for a swap');
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
      noted(out, e, () => failure(e, out, () => go.onclick()));
    } finally {
      go.disabled = false;
      go.textContent = 'Look for a swap';
    }
  };
}

function paintSwap(out, d) {
  const a = d.agent || {};
  const swaps = a.swaps || [];
  const swap = swaps[0];
  const many = swaps.length > 1;
  const names = lineup().concat((a.rejected || []).map((r) => r.film),
    swaps.flatMap((x) => [x.in, x.out]));

  swaps.forEach((x) => {
    const head = el('p', 'work-swap');
    head.appendChild(el('span', 'work-swap-out', x.out));
    head.appendChild(el('span', 'work-swap-arrow', '\u2192'));
    head.appendChild(el('span', 'work-swap-in', x.in));
    out.appendChild(head);
  });

  out.appendChild(drawn(d));

  const split = el('div', 'work-split');
  const left = el('div');

  if (swap) {
    block(left, many ? 'What the swaps do' : 'What the swap does',
      a.verdict || '');
    const take = el('button', 'solid',
      many ? 'Make these swaps' : 'Make this swap');
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
    const rows = el('div');
    side.appendChild(rows);
    const draw = (n) => {
      rows.textContent = '';
      a.rejected.slice(0, n).forEach((r) => {
        const one = el('div', 'turned');
        one.appendChild(el('p', 'turned-name', r.film));
        const why = el('p', 'turned-why');
        withTitles(why, `${r.why.charAt(0).toUpperCase()}${r.why.slice(1)}.`,
          names);
        one.appendChild(why);
        rows.appendChild(one);
      });
    };
    const more = fold(2, a.rejected.length, draw);
    if (more) side.appendChild(more);
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
    all.onclick = () => allVersions();
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
    const acts = el('div', 'row aligned');
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

function allVersions() {
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

  const kept = space.versions || [];
  if (!kept.length) {
    body.appendChild(el('p', 'work-lede',
      'Nothing saved yet. Save a version and it will be listed here.'));
    return;
  }

  body.appendChild(el('p', 'work-lede',
    'Each one is a lineup you saved. Opening a version shows its shape '
    + 'before you decide to use it. Slate keeps your last twenty.'));

  const when = (at) => new Date(at * 1000).toLocaleString('en-GB',
    { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

  kept.forEach((v) => {
    const row = el('div', 'version-row');
    row.appendChild(el('span', 'version-when', when(v.at)));

    const shape = el('span', 'version-shape');
    const bar = el('span', 'version-bar');
    (v.sizes && v.sizes.length ? v.sizes : [1]).forEach((n, i) => {
      const seg = el('span');
      seg.style.flex = String(Math.max(1, n));
      if (i === 0) seg.classList.add('lead');
      bar.appendChild(seg);
    });
    shape.appendChild(bar);
    shape.appendChild(el('span', 'version-what',
      `${v.titles.length} ${nounFor(space.entity_type, v.titles.length)}`
      + (v.groups ? ` \u00b7 ${v.groups} groups` : '')));
    row.appendChild(shape);

    const open = el('button', 'ghost', 'Open');
    open.type = 'button';
    open.onclick = () => previewVersion(v);
    row.appendChild(open);
    body.appendChild(row);
  });
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
  field.placeholder = 'Name the title';
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
      noted(out, e, () => failure(e, out, () => go.onclick()));
    } finally {
      go.disabled = false;
      go.textContent = 'Analyse';
    }
  };
}

function paintStand(out, b) {
  out.textContent = '';
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
  show.onclick = () => showPaper('stand', b);
  acts.append(take, show);
  left.appendChild(acts);

  split.append(left, distanceCard(b.candidate.distances));
  out.appendChild(split);
}

function distanceCard(rows) {
  const side = el('div', 'aside-card');
  side.appendChild(el('p', 'aside-head', 'How far it sits from each'));
  const table = el('table', 'aside-table');
  side.appendChild(table);

  const draw = (n) => {
    table.textContent = '';
    rows.slice(0, n).forEach((x) => {
      const tr = el('tr');
      const td = el('td');
      withTitles(td, x.film, namePool());
      tr.append(td, el('td', 'd', x.distance.toFixed(1)));
      table.appendChild(tr);
    });
  };
  const more = fold(4, rows.length, draw);
  if (more) side.appendChild(more);

  side.appendChild(el('p', 'aside-note',
    'Distance measures shared taste. It does not say why two titles are '
    + 'close.'));
  return side;
}

function compareAsk(body) {
  body.appendChild(el('p', 'fine',
    'The titles you are choosing between, one per line'));
  const area = el('textarea');
  area.className = 'compare-box';
  area.rows = 5;
  area.spellcheck = false;
  area.placeholder = 'Detectorists\nThe Rehearsal\nReservation Dogs\n'
    + 'Starstruck\nSomebody Somewhere';
  body.appendChild(area);

  const form = el('div', 'work-form');
  form.appendChild(el('span', 'fine', 'Room for'));
  const slots = el('select');
  slots.className = 'narrow';
  [1, 2, 3].forEach((n) => slots.appendChild(el('option', null, String(n))));
  slots.value = '2';
  form.appendChild(slots);

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
      noted(out, e, () => failure(e, out, () => go.onclick()));
    } finally {
      go.disabled = false;
      go.textContent = 'Analyse';
    }
  };
}

function paintChoose(out, got) {
  out.textContent = '';
  const best = got.best;
  (got.notes || []).forEach((t) => out.appendChild(el('p', 'work-note', t)));
  out.appendChild(drawn(got.shape));

  const split = el('div', 'work-split ranked');
  const left = el('div');

  const wrap = el('div', 'said');
  wrap.appendChild(el('p', 'said-head', 'Which to take'));
  const names = el('p', 'work-answer');
  withTitles(names, `${nameList(best.films)}.`, namePool());
  wrap.appendChild(names);

  const said = {};
  best.films.forEach((t) => {
    const fresh = inGroup(best.clusters[best.joins[t]]).length === 1;
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
  show.onclick = () => showPaper('choose', got);
  acts.append(take, show);
  left.appendChild(acts);

  const side = el('div', 'aside-card');
  side.appendChild(el('p', 'aside-head', 'Every set, best first'));
  const table = el('table', 'aside-table wide');
  side.appendChild(table);

  const draw = (n) => {
    table.textContent = '';
    const head = el('tr', 'head');
    ['Set', 'Groups', 'Closest', 'Next'].forEach((t) => {
      head.appendChild(el('td', null, t));
    });
    table.appendChild(head);
    got.every.slice(0, n).forEach((r, i) => {
      const tr = el('tr', i ? null : 'win');
      const td = el('td');
      withTitles(td, r.films.join(' + '), namePool());
      tr.append(td, el('td', 'd', String(r.groups)),
        el('td', 'd', r.closest.toFixed(1)),
        el('td', 'd', r.next == null ? '\u2014' : r.next.toFixed(1)));
      table.appendChild(tr);
    });
  };
  const more = fold(3, got.every.length, draw);
  if (more) side.appendChild(more);

  side.appendChild(el('p', 'aside-note',
    'Each set was added and the groups worked out again. Ranked by the '
    + 'closest pair, then by the next closest where that ties.'));

  split.append(left, side);
  out.appendChild(split);
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

function confirmDelete(name) {
  return new Promise((settle) => {
    document.querySelectorAll('.ask-over').forEach((n) => n.remove());

    const over = el('div', 'ask-over');
    over.setAttribute('role', 'dialog');
    over.setAttribute('aria-modal', 'true');

    const box = el('div', 'ask-box');
    box.appendChild(el('h3', 'ask-title', 'Delete this workspace?'));

    const why = el('p', 'ask-said');
    why.appendChild(el('i', null, name));
    why.appendChild(document.createTextNode(
      ' and its saved versions go with it. This cannot be undone.'));
    box.appendChild(why);

    const close = (yes) => {
      over.remove();
      document.body.classList.remove('held');
      document.removeEventListener('keydown', onKey);
      settle(yes);
    };
    const onKey = (ev) => { if (ev.key === 'Escape') close(false); };

    const row = el('div', 'ask-acts');
    const no = el('button', 'ghost', 'Cancel');
    no.type = 'button';
    no.onclick = () => close(false);
    const yes = el('button', 'solid warn', 'Delete');
    yes.type = 'button';
    yes.onclick = () => close(true);
    row.append(no, yes);
    box.appendChild(row);

    over.appendChild(box);
    over.onclick = (ev) => { if (ev.target === over) close(false); };
    document.body.appendChild(over);
    document.body.classList.add('held');
    document.addEventListener('keydown', onKey);
    yes.focus();
  });
}

function showPaper(kind, data) {
  document.querySelectorAll('.paper-over').forEach((n) => n.remove());

  const over = el('div', 'paper-over');
  over.setAttribute('role', 'dialog');
  over.setAttribute('aria-modal', 'true');
  over.setAttribute('aria-label', 'The brief');

  const box = el('div', 'paper');
  const head = el('div', 'paper-head');
  head.appendChild(el('p', 'aside-head', 'The brief'));
  const acts = el('div', 'paper-acts');
  head.appendChild(acts);
  box.appendChild(head);

  const frame = document.createElement('iframe');
  frame.className = 'paper-frame';
  frame.title = 'The brief as it will print';
  box.appendChild(frame);

  const said = el('p', 'aside-note');
  box.appendChild(said);
  over.appendChild(box);
  document.body.appendChild(over);
  document.body.classList.add('held');

  const shut = () => {
    over.remove();
    document.body.classList.remove('held');
    document.removeEventListener('keydown', esc);
  };
  function esc(ev) { if (ev.key === 'Escape') shut(); }
  document.addEventListener('keydown', esc);
  over.onclick = (ev) => { if (ev.target === over) shut(); };

  const close = el('button', 'ghost', 'Close');
  close.type = 'button';
  close.onclick = shut;

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
    acts.append(get, close);
  }).catch((e) => {
    said.textContent = e.message || 'That document could not be made.';
    acts.appendChild(close);
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
