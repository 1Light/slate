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
    `These titles span ${spellCount(info.kinds.length)} kinds.`));
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

const Caps = (t) => t.charAt(0).toUpperCase() + t.slice(1);

const AUDIENCE_SAMPLES = [
  { kind: 'survey_csv', file: 'taste_survey.csv',
    label: 'Try a taste survey' },
  { kind: 'preference_csv', file: 'audience_preferences.csv',
    label: 'Try audience preferences' },
];

const NAME_LIMIT = 60;
const AUDIENCE_STEPS = 4;
const MIN_PICK = 4;
const MAX_PICK = 24;
const SPELT = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
  'eight', 'nine', 'ten', 'eleven', 'twelve'];
const spellCount = (n) => SPELT[n] || String(n);

function modalShell(onShut) {
  document.querySelectorAll('.flow-over').forEach((n) => n.remove());

  const over = el('div', 'flow-over');
  over.setAttribute('role', 'dialog');
  over.setAttribute('aria-modal', 'true');

  const box = el('div', 'flow-box');
  const head = el('div', 'flow-head');
  const bars = el('div', 'flow-bars');
  const marks = [];
  for (let i = 0; i < AUDIENCE_STEPS; i += 1) {
    const one = el('span');
    bars.appendChild(one);
    marks.push(one);
  }
  const line = el('div', 'flow-where');
  const at = el('span', 'flow-at');
  const shut = el('button', 'flow-shut', '\u00d7');
  shut.type = 'button';
  shut.title = 'Close';
  line.append(at, shut);
  head.append(bars, line);

  const body = el('div', 'flow-body');
  const foot = el('div', 'flow-foot');
  const back = el('button', 'ghost', 'Back');
  back.type = 'button';
  const why = el('span', 'flow-why');
  why.setAttribute('role', 'status');
  why.setAttribute('aria-live', 'polite');
  const on = el('button', 'solid', 'Continue');
  on.type = 'button';
  foot.append(back, why, on);

  box.append(head, body, foot);
  over.appendChild(box);

  const close = () => {
    over.remove();
    document.body.classList.remove('held');
    document.removeEventListener('keydown', onKey);
    if (onShut) onShut();
  };
  const onKey = (ev) => { if (ev.key === 'Escape') close(); };
  shut.onclick = close;
  over.onclick = (ev) => { if (ev.target === over) close(); };
  document.body.appendChild(over);
  document.body.classList.add('held');
  document.addEventListener('keydown', onKey);

  return {
    body,
    back,
    on,
    close,
    at(n) {
      marks.forEach((mark, i) => {
        mark.classList.toggle('done', i < n - 1);
        mark.classList.toggle('now', i === n - 1);
      });
      at.textContent = `Step ${n} of ${AUDIENCE_STEPS}`;
    },
    says(text) { why.textContent = text || ''; },
    blocked(stop) {
      on.disabled = !!stop;
    },
  };
}

function audienceModal(found) {
  const kept = { refs: [], pool: [], entity_type: '', slots: 0,
                 mode: 'balanced', candidates: '' };
  const flow = modalShell();
  let at = 1;

  const go = (n) => {
    at = n;
    flow.at(n);
    flow.body.textContent = '';
    flow.back.hidden = n === 1;
    flow.on.textContent = n === 4 ? 'Build this lineup' : 'Continue';
    flow.says('');
    flow.blocked(false);
    if (n === 1) stepReview(flow, found, kept, () => go(2));
    else if (n === 2) stepCandidates(flow, kept, () => go(3));
    else if (n === 3) stepSlots(flow, kept, () => go(4));
    else stepMode(flow, found, kept);
  };
  flow.back.onclick = () => go(Math.max(1, at - 1));
  go(1);
}

function flowHead(flow, title, said) {
  flow.body.appendChild(el('h3', 'flow-title', title));
  if (said) flow.body.appendChild(el('p', 'flow-said', said));
}

function stepReview(flow, found, kept, next) {
  const got = found.review;
  const dropped = new Set();
  const kinds = got.groups.map((g) => g.label);

  flowHead(flow, 'What Slate understood',
    `${Caps(spellCount(got.count))} ${got.count === 1 ? 'reference' : 'references'} `
    + `across ${nameList(kinds)}. Remove anything it read wrongly.`);

  const all = [];
  got.groups.forEach((g) => g.references.forEach((r) => all.push(r)));

  const tell = () => {
    const left = all.length - dropped.size;
    flow.says(`${left} ${left === 1 ? 'reference' : 'references'} will be used`);
    flow.blocked(left === 0);
  };

  const cols = el('div', 'flow-cols');
  got.groups.forEach((group) => {
    const col = el('div');
    col.appendChild(el('p', 'flow-kind',
      `${Caps(group.label)} \u00b7 ${group.references.length}`));
    group.references.forEach((ref) => {
      const row = el('div', 'flow-ref');
      row.appendChild(el('span', 'flow-ref-name', ref.title));
      const off = el('button', 'flow-ref-off', '\u00d7');
      off.type = 'button';
      off.onclick = () => {
        const out = dropped.has(ref.entity_id);
        if (out) dropped.delete(ref.entity_id);
        else dropped.add(ref.entity_id);
        row.classList.toggle('out', !out);
        off.textContent = out ? '\u00d7' : '\u21ba';
        off.title = out ? `Leave ${ref.title} out` : `Put ${ref.title} back`;
        tell();
      };
      off.title = `Leave ${ref.title} out`;
      row.appendChild(off);
      col.appendChild(row);
    });
    cols.appendChild(col);
  });
  flow.body.appendChild(cols);

  const left = (got.unresolved || []).concat(got.negative_only || []);
  if (left.length) {
    const band = el('div', 'flow-aside');
    band.appendChild(el('p', 'flow-kind', `Not used \u00b7 ${left.length}`));
    const grouped = new Map();
    left.forEach((item) => {
      const why = item.why || 'could not be matched';
      grouped.set(why, (grouped.get(why) || []).concat(item.name));
    });
    grouped.forEach((names, why) => {
      const said = el('p', 'flow-said');
      withTitles(said, `${nameList(names)} `
        + `${names.length === 1 ? 'was' : 'were'} ${why}.`, names);
      band.appendChild(said);
    });
    flow.body.appendChild(band);
  }

  tell();
  flow.on.onclick = () => {
    kept.refs = all.filter((r) => !dropped.has(r.entity_id));
    if (!kept.refs.length) return;
    next();
  };
}

function stepCandidates(flow, kept, next) {
  flowHead(flow, 'What can Slate choose from?');
  flow.body.appendChild(el('p', 'aguide',
    'Enter the candidates Slate can choose from, one per line. The final '
    + 'lineup will contain one type: films, music artists, books, '
    + 'podcasts or TV shows.'));

  const area = el('textarea', 'afield');
  area.setAttribute('aria-label', 'Candidate titles');
  area.spellcheck = false;
  area.value = kept.candidates || '';
  area.placeholder = 'Ex Machina\nMoon\nPrimer';
  flow.body.appendChild(area);

  const row = el('div', 'row');
  const look = el('button', 'solid', 'Analyse candidates');
  look.type = 'button';
  const sample = el('button', 'linky', 'Use an example pool');
  sample.type = 'button';
  row.append(look, sample);
  flow.body.appendChild(row);

  const out = el('div', 'flow-out');
  out.setAttribute('aria-live', 'polite');
  flow.body.appendChild(out);

  let revision = 0;
  let reading = false;
  const invalidate = () => {
    revision += 1;
    kept.candidates = area.value;
    kept.pool = [];
    kept.entity_type = '';
    out.textContent = '';
    flow.says('Analyse the candidates first');
    flow.blocked(true);
  };
  area.addEventListener('input', invalidate);
  invalidate();

  sample.onclick = async () => {
    const requestedAt = revision;
    try {
      const got = await ask('/api/examples/sf-candidates');
      if (requestedAt !== revision || !area.isConnected) return;
      area.value = got.titles.join('\n');
      invalidate();
    } catch { }
  };

  const settle = (titles, entityType, label) => {
    kept.pool = titles;
    kept.entity_type = entityType;
    kept.slots = Math.min(titles.length, Math.max(MIN_PICK,
      kept.slots || Math.min(8, titles.length)));
    flow.says(`${titles.length} ${label}`);
    flow.blocked(false);
  };

  look.onclick = async () => {
    if (reading) return;
    invalidate();
    const requestedAt = revision;
    const titles = area.value.split('\n').map((t) => t.trim())
      .filter(Boolean);
    if (titles.length < MIN_PICK) {
      out.textContent = '';
      out.appendChild(el('p', 'work-note refused',
        `Give Slate at least ${MIN_PICK} candidates.`));
      return;
    }
    reading = true;
    look.disabled = true;
    look.classList.add('busy');
    look.textContent = 'Reading';
    out.textContent = '';
    try {
      const got = await ask('/api/audience/candidates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidates: titles }),
      });
      if (requestedAt !== revision || !area.isConnected) return;
      drawPool(out, got, settle);
    } catch (e) {
      if (requestedAt === revision && area.isConnected) {
        out.appendChild(el('p', 'work-note refused',
          e.message || 'Those could not be read.'));
      }
    } finally {
      reading = false;
      look.disabled = false;
      look.classList.remove('busy');
      look.textContent = 'Analyse candidates';
    }
  };

  flow.on.onclick = () => { if (!flow.on.disabled && kept.pool.length) next(); };
}

function drawPool(out, got, settle) {
  out.textContent = '';
  const usable = got.kinds.filter((k) => k.enough);

  if (got.kinds.length === 1 && usable.length === 1) {
    const only = got.kinds[0];
    out.appendChild(el('p', 'flow-said',
      `All matched candidates are ${only.label}. Click Continue to `
      + 'proceed.'));
    if ((got.missing || []).length) out.appendChild(missedLine(got.missing));
    settle(only.titles.map((t) => t.title), only.entity_type, only.label);
    return;
  }

  const fig = el('div', 'taste');
  fig.appendChild(el('p', 'mixed-lede',
    `Qloo matched these to ${spellCount(got.kinds.length)} kinds.`));
  fig.appendChild(el('p', 'mixed-why',
    'A lineup holds one kind, so pick which to choose from.'));

  const cols = el('div', 'mixed-cols');
  got.kinds.forEach((kind) => {
    const col = el('div');
    col.appendChild(el('p', 'mixed-head',
      `Matched as ${kind.label} \u00b7 ${kind.titles.length}`));
    kind.titles.slice(0, 3).forEach((t) => {
      const line = el('p', 'taste-film');
      line.appendChild(document.createTextNode(t.title));
      if (t.year) line.appendChild(el('span', 'year', String(t.year)));
      col.appendChild(line);
    });
    if (kind.titles.length > 3) {
      col.appendChild(el('p', 'mixed-short',
        `and ${kind.titles.length - 3} more`));
    }
    if (kind.enough) {
      const use = el('button', 'mixed-use', `Use these ${kind.titles.length}`);
      use.type = 'button';
      use.onclick = () => {
        [...cols.querySelectorAll('.mixed-use')].forEach((b) => {
          b.classList.toggle('on', b === use);
        });
        settle(kind.titles.map((t) => t.title), kind.entity_type,
               kind.label);
      };
      col.appendChild(use);
    } else {
      col.appendChild(el('p', 'mixed-short', `Needs ${MIN_PICK}.`));
    }
    cols.appendChild(col);
  });
  fig.appendChild(cols);
  out.appendChild(fig);
  if ((got.missing || []).length) out.appendChild(missedLine(got.missing));
}

function missedLine(missing) {
  const line = el('p', 'flow-said');
  withTitles(line, `${nameList(missing)} could not be matched.`, missing);
  return line;
}

function stepSlots(flow, kept, next) {
  const most = Math.min(kept.pool.length, MAX_PICK);
  const label = kept.entity_type ? nounFor(kept.entity_type, most) : 'titles';
  kept.slots = Math.min(most, Math.max(MIN_PICK, kept.slots || 8));

  flowHead(flow, 'How many should Slate select?',
    `${Caps(spellCount(kept.pool.length))} ${label} matched. Slate will `
    + 'choose the ones that best fit your audience.');

  const row = el('div', 'flow-stepper');
  const less = el('button', 'flow-step-btn', '\u2212');
  less.type = 'button';
  const count = el('span', 'flow-count');
  const more = el('button', 'flow-step-btn', '+');
  more.type = 'button';
  const range = el('span', 'flow-range');
  row.append(less, count, more, range);
  flow.body.appendChild(row);

  const bar = el('div', 'flow-share');
  const taken = el('span');
  const spare = el('span', 'spare');
  bar.append(taken, spare);
  flow.body.appendChild(bar);

  const said = el('p', 'flow-said');
  flow.body.appendChild(said);
  flow.body.appendChild(el('p', 'flow-note',
    'A lineup can contain 4\u201324 titles, depending on how many '
    + 'candidates are available.'));

  const tell = () => {
    count.textContent = String(kept.slots);
    range.textContent = `of ${kept.pool.length}, between ${MIN_PICK} `
      + `and ${most}`;
    taken.style.flex = String(kept.slots);
    spare.style.flex = String(Math.max(0, kept.pool.length - kept.slots));
    const unused = kept.pool.length - kept.slots;
    said.textContent = unused
      ? `Slate selects ${kept.slots}, and leaves ${unused} unused.`
      : `Slate selects all ${kept.slots}.`;
    less.disabled = kept.slots <= MIN_PICK;
    more.disabled = kept.slots >= most;
    flow.says(`${kept.slots} of ${kept.pool.length} ${label}`);
  };
  less.onclick = () => { kept.slots -= 1; tell(); };
  more.onclick = () => { kept.slots += 1; tell(); };
  tell();

  flow.on.onclick = next;
}

function stepMode(flow, found, kept) {
  flowHead(flow, 'How should Slate build your lineup?');

  const modes = el('div', 'flow-modes');
  modes.setAttribute('role', 'group');
  modes.setAttribute('aria-label', 'How Slate should build the lineup');
  [['balanced', 'Balanced',
    'Give the different tastes in your audience equal weight.',
    'Less common tastes get as much consideration as popular ones.'],
   ['demand_led', 'Demand-led',
    'Give more weight to the preferences with the strongest support.',
    'Popular tastes get more consideration than less common ones.']]
    .forEach(([value, title, why, explanation]) => {
      const pick = el('label', 'flow-mode' + (value === kept.mode ? ' on' : ''));
      const heading = el('span', 'flow-mode-heading');
      heading.appendChild(el('span', 'flow-mode-name', title));
      const radio = el('input', 'flow-mode-dot');
      radio.type = 'radio';
      radio.name = 'audience-build-mode';
      radio.value = value;
      radio.checked = value === kept.mode;
      heading.appendChild(radio);
      pick.appendChild(heading);
      pick.appendChild(el('span', 'flow-mode-why', why));
      pick.appendChild(el('span', 'flow-mode-explanation', explanation));
      radio.onchange = () => {
        kept.mode = value;
        [...modes.children].forEach((c) => c.classList.toggle('on',
          c === pick));
      };
      modes.appendChild(pick);
    });
  flow.body.appendChild(modes);

  const note = el('p', 'work-note');
  flow.body.appendChild(note);

  flow.on.onclick = async () => {
    flow.on.classList.add('busy');
    flow.on.textContent = 'Building';
    note.classList.remove('refused');
    note.textContent = 'Asking Qloo how these fit the audience.';
    try {
      const made = await ask('/api/audience/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner: owner(),
          references: kept.refs,
          candidates: kept.pool,
          entity_type: kept.entity_type,
          slots: kept.slots,
          mode: kept.mode,
          audience: {
            source: found.kind,
            filename: found.filename,
            synthetic: found.synthetic,
            text: found.text || '',
            unresolved: found.review.unresolved,
            negative_only: found.review.negative_only,
          },
        }),
      });
      window.location.href = `/app#${made.id}`;
      window.location.reload();
    } catch (e) {
      note.textContent = e.message || 'That did not work.';
      note.classList.add('refused');
    } finally {
      flow.on.classList.remove('busy');
      flow.on.textContent = 'Build this lineup';
    }
  };
}

function audienceFlow(host) {
  host.textContent = '';
  const found = { review: null, kind: null, filename: '', synthetic: false };

  const layout = el('div', 'audience-entry');
  const form = el('div', 'audience-entry-form');
  layout.appendChild(form);
  host.appendChild(layout);

  const tabs = el('div', 'aswitch');
  const asText = el('button', 'aswitch-half on', 'Describe your audience');
  asText.type = 'button';
  asText.setAttribute('aria-pressed', 'true');
  const asFile = el('button', 'aswitch-half', 'Use customer data');
  asFile.type = 'button';
  asFile.setAttribute('aria-pressed', 'false');
  tabs.append(asText, asFile);
  form.appendChild(tabs);

  const textWay = el('div');
  const descriptionLabel = el('label', 'audience-entry-label',
    'What does your audience like?');
  descriptionLabel.htmlFor = 'audience-description';
  textWay.appendChild(descriptionLabel);
  textWay.appendChild(el('p', 'aguide',
    'Name films, artists, books, podcasts or TV shows they enjoy.'));
  const area = el('textarea', 'afield');
  area.id = 'audience-description';
  area.spellcheck = false;
  area.placeholder = 'They love Arrival and listen to a lot of Radiohead.';
  textWay.appendChild(area);
  form.appendChild(textWay);

  const reads = el('aside', 'audience-entry-guide');
  reads.setAttribute('aria-label', 'What Slate reads');
  reads.appendChild(el('p', 'audience-entry-eyebrow', 'What Slate reads'));
  const point = (title, said) => {
    const section = el('section');
    section.appendChild(el('h2', null, title));
    section.appendChild(el('p', null, said));
    reads.appendChild(section);
  };
  point('Names, not adjectives',
    'Slate takes the titles you name and looks each one up in Qloo. '
    + '\u201cThoughtful science fiction\u201d gives it nothing to look up; '
    + 'Arrival gives it a great deal.');
  point('Any of the five kinds',
    'Films, music artists, books, podcasts and TV shows all count as '
    + 'evidence, whichever kind you end up selecting.');
  reads.appendChild(el('p', 'audience-entry-purpose',
    'You will see every name Slate found, and can remove anything it read '
    + 'wrongly, before it selects.'));
  layout.appendChild(reads);

  const fileWay = el('div');
  fileWay.hidden = true;
  const guide = el('aside', 'audience-entry-guide');
  guide.hidden = true;
  guide.setAttribute('aria-label', 'Accepted CSV formats');
  guide.appendChild(el('p', 'audience-entry-eyebrow',
    'Two accepted CSV formats'));
  const shape = (title, said, cols) => {
    const section = el('section');
    section.appendChild(el('h2', null, title));
    section.appendChild(el('p', null, said));
    section.appendChild(el('span', 'audience-entry-required',
      'Required columns'));
    const columns = el('div', 'audience-entry-columns');
    cols.forEach((name) => {
      columns.appendChild(el('code', null, name));
    });
    section.appendChild(columns);
    guide.appendChild(section);
  };
  shape('Survey CSV format',
    'What your audience said about films, artists, books, podcasts or TV '
    + 'shows.', ['question', 'response']);
  shape('Audience preferences CSV format',
    'How many positive and negative responses each film, artist, book, '
    + 'podcast or TV show received.',
    ['name', 'liked_count', 'disliked_count']);
  guide.appendChild(el('p', 'audience-entry-purpose',
    'Slate uses these preferences across media types to help select a '
    + 'lineup from your candidate pool in one chosen category.'));
  layout.appendChild(guide);

  fileWay.appendChild(el('p', 'audience-entry-label',
    'Upload your audience data'));
  fileWay.appendChild(el('p', 'aguide',
    'Choose a CSV file, or start with a sample below.'));

  const upload = document.createElement('input');
  upload.type = 'file';
  upload.accept = '.csv,text/csv';
  upload.className = 'ahidden';
  upload.onchange = () => {
    const file = upload.files && upload.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => loaded(file.name, String(reader.result), null,
                                 false);
    reader.readAsText(file);
  };
  fileWay.appendChild(upload);

  const uploadBox = el('div', 'audience-entry-upload');
  const choose = el('button', 'ghost', 'Choose a CSV file');
  choose.type = 'button';
  choose.onclick = () => upload.click();
  uploadBox.appendChild(choose);
  uploadBox.appendChild(el('p', null, 'Survey answers or audience preferences'));
  fileWay.appendChild(uploadBox);
  fileWay.appendChild(el('p', 'audience-entry-samples-label',
    'Or try synthetic demo data'));
  const picks = el('div', 'acards audience-entry-samples');
  const card = (title, why, dashed) => {
    const one = el('button', dashed ? 'acard dashed' : 'acard');
    one.type = 'button';
    one.appendChild(el('span', 'acard-name', title));
    one.appendChild(el('span', 'acard-why', why));
    picks.appendChild(one);
    return one;
  };
  card('Try a taste survey', 'Questions and audience responses').onclick =
    () => grab('taste_survey.csv', 'survey_csv');
  card('Try audience preferences',
       'Positive and negative response totals').onclick =
    () => grab('audience_preferences.csv', 'preference_csv');
  fileWay.appendChild(picks);

  const chosen = el('div', 'achosen');
  chosen.hidden = true;
  fileWay.appendChild(chosen);
  form.appendChild(fileWay);

  const go = el('button', 'solid', 'Analyse audience');
  go.type = 'button';
  form.appendChild(go);

  const note = el('p', 'work-note');
  note.setAttribute('role', 'status');
  note.setAttribute('aria-live', 'polite');
  form.appendChild(note);
  const said = (text, bad) => {
    note.textContent = text || '';
    note.classList.toggle('refused', !!bad);
  };

  let holding = null;

  async function grab(name, kind) {
    try {
      const got = await fetch(`/api/examples/audience/${name}`);
      loaded(name, await got.text(), kind, true);
    } catch { said('That example could not be loaded.', true); }
  }

  function loaded(filename, text, kind, synthetic) {
    holding = { filename, text, kind, synthetic };
    chosen.hidden = false;
    chosen.textContent = '';

    const head = el('div', 'achosen-head');
    const name = el('span', 'achosen-name');
    name.appendChild(document.createTextNode(filename));
    if (synthetic) {
      name.appendChild(el('span', 'atag', 'Synthetic demo data'));
    }
    head.appendChild(name);

    const acts = el('span', 'achosen-acts');
    const drop = el('button', 'linky', 'Remove');
    drop.type = 'button';
    drop.onclick = () => {
      holding = null;
      chosen.hidden = true;
      upload.value = '';
      said('');
    };
    acts.appendChild(drop);
    head.appendChild(acts);
    chosen.appendChild(head);
    said('');
  }

  asText.onclick = () => {
    asText.classList.add('on');
    asFile.classList.remove('on');
    asText.setAttribute('aria-pressed', 'true');
    asFile.setAttribute('aria-pressed', 'false');
    guide.hidden = true;
    reads.hidden = false;
    textWay.hidden = false;
    fileWay.hidden = true;
  };
  asFile.onclick = () => {
    asFile.classList.add('on');
    asText.classList.remove('on');
    asText.setAttribute('aria-pressed', 'false');
    asFile.setAttribute('aria-pressed', 'true');
    guide.hidden = false;
    reads.hidden = true;
    fileWay.hidden = false;
    textWay.hidden = true;
  };

  go.onclick = async () => {
    const usingText = !textWay.hidden;
    if (usingText && !area.value.trim()) {
      said('Describe the audience first.', true);
      return;
    }
    if (!usingText && !holding) {
      said('Choose a file, or try one of the examples.', true);
      return;
    }
    go.classList.add('busy');
    go.textContent = 'Reading';
    said('');
    try {
      const got = await ask('/api/audience/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(usingText
          ? { kind: 'description', text: area.value }
          : { kind: holding.kind || '', text: holding.text,
              filename: holding.filename, synthetic: holding.synthetic }),
      });
      found.review = got;
      found.kind = got.kind;
      found.text = usingText ? area.value : '';
      found.filename = got.filename;
      found.synthetic = got.synthetic;
      audienceModal(found);
    } catch (e) {
      said(e.message || 'That could not be read.', true);
    } finally {
      go.classList.remove('busy');
      go.textContent = 'Analyse audience';
    }
  };
}

function asTable(text) {
  const table = el('table', 'pairs');
  text.split('\n').slice(0, 7).forEach((line, i) => {
    if (!line.trim()) return;
    const tr = el('tr', i === 0 ? 'head' : null);
    (line.match(/("[^"]*"|[^,]+)/g) || []).forEach((cell) => {
      tr.appendChild(el('td', null, cell.replace(/^"|"$/g, '').trim()));
    });
    table.appendChild(tr);
  });
  return table;
}

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

  const paths = el('span', 'deskbar-paths');
  const onLineup = el('button', 'door-path on', 'Analyse a lineup');
  onLineup.type = 'button';
  const onAudience = el('button', 'door-path', 'Build for an audience');
  onAudience.type = 'button';
  paths.append(onLineup, onAudience);
  if (here) here.appendChild(paths);

  const head = el('div', 'door-top');
  head.appendChild(el('h1', 'door-title', 'Start with a lineup.'));
  head.appendChild(el('p', 'door-lede',
    'Four to twenty-four titles, one per line. Films, music, books, '
    + 'podcasts or TV shows. In case a name exists in more than one type, '
    + 'adding a year in brackets, like Monster (2023), helps Slate find the '
    + 'one you mean.'));
  top.appendChild(head);

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

  const forAudience = el('div', 'door-audience');
  forAudience.hidden = true;
  top.appendChild(forAudience);
  stage.appendChild(top);

  const lineupBits = [pair];

  const turnTo = (which) => {
    const audience = which === 'audience';
    onLineup.classList.toggle('on', !audience);
    onAudience.classList.toggle('on', audience);
    lineupBits.forEach((n) => { n.hidden = audience; });
    forAudience.hidden = !audience;
    if (audience && !forAudience.children.length) audienceFlow(forAudience);
    document.querySelector('.door-title').textContent = audience
      ? 'Build a lineup for your audience'
      : 'Start with a lineup.';
    document.querySelector('.door-lede').textContent = audience
      ? 'Describe their tastes, upload survey answers or preference data, '
        + 'then provide the candidates. Slate will help choose which ones '
        + 'to include in your lineup.'
      : 'Four to twenty-four titles, one per line. Films, music, books, '
        + 'podcasts or TV shows. In case a name exists in more than one '
        + 'type, adding a year in brackets, like Monster (2023), helps '
        + 'Slate find the one you mean.';
  };
  onLineup.onclick = () => turnTo('lineup');
  onAudience.onclick = () => turnTo('audience');

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

  const head = el('div', 'door-card-head');
  const bar = el('div', 'door-card-bar');
  (w.sizes && w.sizes.length ? w.sizes : [1]).forEach((n, i) => {
    const seg = el('span');
    seg.style.flex = String(Math.max(1, n));
    if (i === 0) seg.classList.add('lead');
    bar.appendChild(seg);
  });
  head.appendChild(bar);
  card.appendChild(head);

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

  const more = el('button', 'door-card-more');
  more.type = 'button';
  for (let i = 0; i < 3; i += 1) more.appendChild(el('span'));
  more.setAttribute('aria-label', `More for ${w.name}`);
  more.setAttribute('aria-expanded', 'false');
  head.appendChild(more);

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
    const was = space;
    const got = await ask(`/api/spaces/${space.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner: owner(), ...fields }),
    });
    if (!Array.isArray(got.locked)) {
      got.locked = Array.isArray(fields.locked) ? fields.locked
        : (was.locked || []);
    }
    if (got.audience === undefined) got.audience = was.audience;
    space = got;
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
  title.oninput = () => {
    const text = title.textContent || '';
    if (text.length <= NAME_LIMIT) return;
    title.textContent = text.slice(0, NAME_LIMIT);
    const at = document.createRange();
    at.selectNodeContents(title);
    at.collapse(false);
    const picked = window.getSelection();
    picked.removeAllRanges();
    picked.addRange(at);
  };
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
  const audience = space.audience || null;
  const label = !audience ? 'Lineup analysis'
    : audience.mode === 'demand_led' ? 'Audience \u00b7 Demand-led'
      : 'Audience \u00b7 Balanced';

  here.appendChild(el('span', 'deskbar-slash', '\u00a0/\u00a0'));
  here.appendChild(title);
  here.appendChild(el('span', 'deskbar-mode', label));

  end.appendChild(el('span', 'deskbar-counts'));

  const resetBtn = el('button', 'ghost', 'Reset lineup');
  resetBtn.type = 'button';
  resetBtn.hidden = true;
  drawSpace.updateResetTooltip = () => {
    resetBtn.title = (space.versions || []).length
      ? 'Restore your most recently saved lineup.'
      : 'Restore the lineup you opened this workspace with.';
  };
  drawSpace.updateResetTooltip();
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

  const saveBtn = el('button', 'solid save-version');
  saveBtn.type = 'button';
  saveBtn.setAttribute('aria-label', 'Save version');
  const saveLabel = el('span', 'save-version-label', 'Save version');
  const saveConfirmation = el('span', 'save-version-confirmation', '\u2713 Saved');
  saveLabel.setAttribute('aria-hidden', 'true');
  saveConfirmation.setAttribute('aria-hidden', 'true');
  saveBtn.append(saveLabel, saveConfirmation);
  let savedTimer;
  const clearSaved = () => {
    clearTimeout(savedTimer);
    saveBtn.classList.remove('is-saved');
    saveBtn.setAttribute('aria-label', 'Save version');
  };
  saveBtn.onclick = async () => {
    clearSaved();
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
      const previous = (space.versions || [])[0];
      space = got;
      drawVersions();
      const latest = (space.versions || [])[0];
      if (latest && (!previous || latest.at !== previous.at)) {
        saveBtn.classList.add('is-saved');
        saveBtn.setAttribute('aria-label', '\u2713 Saved');
        said('Version saved.');
        savedTimer = setTimeout(clearSaved, 2000);
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
  rail.appendChild(el('p', 'desk-rail-what',
    'Lock any titles Slate must include.'));
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

  if (space.audience) {
    const tab = el('button', 'ask');
    tab.type = 'button';
    tab.dataset.ask = 'audience';
    tab.appendChild(el('span', 'ask-what', 'Audience'));
    tab.appendChild(el('span', 'ask-why',
      'The evidence this lineup was built from'));
    tab.onclick = () => (openAsk === 'audience' ? closeAsk()
      : showAsk('audience'));
    rail.appendChild(tab);
  }

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
  document.querySelectorAll('.film-lock-tip').forEach((n) => n.remove());
  openAsk = key;
  markAsk();
  work.textContent = '';
  const head = el('div', 'work-head');
  const named = ASKS.find(([k]) => k === key);
  head.appendChild(el('h2', 'work-title',
    named ? named[1] : 'Audience'));
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
  else if (key === 'audience') audienceTab(body);
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
const LOCK_OPEN = '<svg width="11" height="13" viewBox="0 0 11 13" '
  + 'aria-hidden="true"><rect x="0.6" y="5.4" width="9.8" height="7.1" '
  + 'rx="1.6" fill="currentColor"/><path d="M2.9 5.4V3.6a2.6 2.6 0 0 1 '
  + '5.2 0" stroke="currentColor" stroke-width="1.3" fill="none"/></svg>';
const LOCK_SHUT = '<svg width="11" height="13" viewBox="0 0 11 13" '
  + 'aria-hidden="true"><rect x="0.6" y="5.4" width="9.8" height="7.1" '
  + 'rx="1.6" fill="currentColor"/><path d="M2.9 5.4V3.6a2.6 2.6 0 0 1 '
  + '5.2 0v1.8" stroke="currentColor" stroke-width="1.3" '
  + 'fill="none"/></svg>';
const locked = () => ((space && space.locked) || [])
  .filter((t) => lineup().includes(t));

function drawChips() {
  chipBox.textContent = '';
  const all = lineup();
  const show = chipsOpen ? all : all.slice(0, CHIPS_SHOWN);
  const lost = new Set((shown && shown.unresolved) || []);
  const held = new Set(locked());
  show.forEach((t) => {
    const chip = el('span', lost.has(t) ? 'chip lost' : 'chip');
    if (held.has(t)) chip.classList.add('held');

    const hold = el('button', 'chip-lock');
    hold.type = 'button';
    hold.innerHTML = held.has(t) ? LOCK_SHUT : LOCK_OPEN;
    hold.title = held.has(t)
      ? 'This title must be included. Click to unlock.'
      : 'Always include this title in the lineup.';
    hold.onclick = async () => {
      const want = held.has(t) ? [...held].filter((x) => x !== t)
        : [...held, t];
      await save({ locked: want });
      drawChips();
      runSpace();
    };

    const name = el('span', 'chip-name', t);
    if (lost.has(t)) name.title = `Qloo could not place ${t}`;

    const off = el('button', 'chip-x', '\u00d7');
    off.type = 'button';
    off.title = `Remove ${t}`;
    off.onclick = async () => {
      await save({
        titles: all.filter((x) => x !== t),
        locked: [...held].filter((x) => x !== t),
      });
      drawChips();
      drawSpace.drawKeep();
      runSpace();
    };

    chip.append(hold, name, off);
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
    locked: locked(),
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
  document.querySelectorAll('.film-lock-tip').forEach((n) => n.remove());
  d.locked = locked();
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

window.afterLinks = (where) => markLocks(where);

function markLocks(where) {
  const held = new Set(locked());
  if (!held.size) return;
  where.querySelectorAll('[data-title]').forEach((row) => {
    if (!held.has(row.dataset.title)) return;
    row.classList.add('held');
    const mark = el('span', 'film-lock');
    mark.innerHTML = LOCK_SHUT;
    mark.tabIndex = 0;
    mark.setAttribute('role', 'img');
    mark.setAttribute('aria-label', 'Locked — Slate must keep this title.');
    const hint = el('span', 'film-lock-tip',
      'Locked — Slate must keep this title.');
    hint.setAttribute('aria-hidden', 'true');
    const placeHint = () => {
      document.querySelectorAll('.film-lock-tip').forEach((n) => n.remove());
      document.body.appendChild(hint);
      const rect = mark.getBoundingClientRect();
      hint.style.left = `${Math.max(8, Math.min(rect.left,
        window.innerWidth - hint.offsetWidth - 8))}px`;
      hint.style.top = `${Math.max(8, rect.bottom + hint.offsetHeight + 8
        > window.innerHeight ? rect.top - hint.offsetHeight - 8
        : rect.bottom + 8)}px`;
    };
    mark.onmouseenter = placeHint;
    mark.onfocus = placeHint;
    mark.onmouseleave = () => {
      if (document.activeElement !== mark) hint.remove();
    };
    mark.onblur = () => {
      if (!mark.matches(':hover')) hint.remove();
    };
    row.insertBefore(mark, row.firstChild);
  });
}

function drawn(d) {
  d.locked = locked();
  const sec = chapter(d, null);
  sec.classList.add('shown');
  ['.chapter-title', '.verdict-line'].forEach((sel) => {
    const gone = sec.querySelector(sel);
    if (gone) gone.remove();
  });
  markLocks(sec);
  return sec;
}

const AUD_KINDS = {
  'urn:entity:movie': 'Film',
  'urn:entity:tv_show': 'TV show',
  'urn:entity:artist': 'Music artist',
  'urn:entity:book': 'Book',
  'urn:entity:podcast': 'Podcast',
};

function audCard(host, label, name, said, tag) {
  const card = el('div', 'aud-card');
  card.appendChild(el('p', 'aud-card-label', label));
  const line = el('p', 'aud-card-name');
  line.appendChild(document.createTextNode(name));
  if (tag) line.appendChild(el('span', 'aud-card-tag', tag));
  card.appendChild(line);
  if (said) card.appendChild(el('p', 'aud-card-said', said));
  host.appendChild(card);
}

function audienceTab(body) {
  const a = space.audience || {};
  const demand = a.mode === 'demand_led';
  const aggregated = a.source === 'preference_csv';
  const survey = a.source === 'survey_csv';
  body.classList.add('audience-body');

  const served = new Map((a.served || []).map((row) =>
    [row.reference, row.by]));
  const refs = (a.references || []).slice();
  const named = new Set(refs.map((r) => r.title));
  served.forEach((by, title) => {
    if (!named.has(title)) refs.push({ title, sources: [] });
  });

  const cards = el('div', 'aud-cards');
  audCard(cards, 'Mode', demand ? 'Demand-led' : 'Balanced',
    demand ? 'More weight to the strongest support'
      : 'Equal weight to the different tastes');
  const kinds = new Set(refs.map((r) => AUD_KINDS[r.entity_type])
    .filter(Boolean));
  audCard(cards, 'Source',
    a.filename || 'Your description',
    `${refs.length} ${refs.length === 1 ? 'reference' : 'references'}`
    + (kinds.size > 1 ? ` across ${kinds.size} kinds` : ''),
    a.synthetic ? 'Synthetic' : '');
  body.appendChild(cards);

  if (refs.length) {
    body.appendChild(el('p', 'aud-intro',
      'Closest matches in your selected lineup, based on Qloo rankings.'));

    const table = el('table', 'aud-table' + (aggregated ? ' aud-counts' : ''));
    table.setAttribute('aria-label',
      'Audience references and lineup matches');
    const head = el('thead');
    const headings = el('tr');
    ['Audience reference', 'Closest lineup match',
      ...(aggregated ? ['Liked', 'Disliked'] : [''])]
      .forEach((label, i) => {
        const cell = el('th', aggregated && i > 1 ? 'aud-number' : null,
                        label);
        cell.scope = 'col';
        headings.appendChild(cell);
      });
    head.appendChild(headings);

    const rows = el('tbody');
    refs.forEach((r, index) => {
      const row = el('tr');
      const name = el('td', 'aud-reference');
      name.appendChild(document.createTextNode(r.title));
      const info = [];
      if (AUD_KINDS[r.entity_type]) info.push(AUD_KINDS[r.entity_type]);
      if (survey && Number.isFinite(Number(r.weight))) {
        const count = Math.round(Number(r.weight));
        info.push(`${count} ${count === 1 ? 'mention' : 'mentions'}`);
      }
      if (info.length) {
        name.appendChild(el('span', 'aud-meta', info.join(' \u00b7 ')));
      }
      row.appendChild(name);
      row.appendChild(el('td', null, served.get(r.title) || '\u2014'));
      rows.appendChild(row);

      if (aggregated) {
        row.appendChild(el('td', 'aud-number', r.weight == null
          ? '\u2014' : String(Math.round(r.weight))));
        row.appendChild(el('td', 'aud-number aud-against',
          String(r.disliked || 0)));
        return;
      }

      const action = el('td', 'aud-action');
      row.appendChild(action);
      const sources = (r.sources || []).filter((src) => src.quote);
      if (!sources.length) {
        action.appendChild(el('span', 'aud-no-evidence', '\u2014'));
        return;
      }

      const toggle = el('button', 'linky aud-evidence-toggle',
                        'View evidence');
      toggle.type = 'button';
      toggle.setAttribute('aria-label', `View evidence for ${r.title}`);
      toggle.setAttribute('aria-expanded', 'false');

      const evidence = el('tr', 'aud-evidence');
      evidence.id = `audience-evidence-${index}`;
      evidence.hidden = true;
      toggle.setAttribute('aria-controls', evidence.id);
      const cell = el('td');
      cell.colSpan = 3;
      sources.forEach((src) => {
        const quote = el('p', 'aud-evidence-quote');
        if (src.liked === false) {
          quote.appendChild(el('span', 'aud-evidence-polarity',
                               'Negative mention: '));
        }
        quote.appendChild(document.createTextNode(`\u201c${src.quote}\u201d`));
        cell.appendChild(quote);
      });
      evidence.appendChild(cell);
      toggle.onclick = () => {
        evidence.hidden = !evidence.hidden;
        toggle.setAttribute('aria-expanded', String(!evidence.hidden));
        toggle.textContent = evidence.hidden ? 'View evidence'
          : 'Hide evidence';
        toggle.setAttribute('aria-label',
          `${evidence.hidden ? 'View' : 'Hide'} evidence for ${r.title}`);
      };
      action.appendChild(toggle);
      rows.appendChild(evidence);
    });

    table.append(head, rows);
    body.appendChild(table);

    if (survey || aggregated) {
      body.appendChild(el('p', 'aud-note', survey
        ? 'Mentions are from survey answers; they do not necessarily '
          + 'represent unique people.'
        : 'Counts are taken from your file. The same person may be '
          + 'represented under several items.'));
    }
  }

  const left = (a.unresolved || []).concat(a.negative_only || []);
  if (left.length) {
    const details = el('details', 'aud-unused');
    details.appendChild(el('summary', null, `Not used \u00b7 ${left.length} `
      + `${left.length === 1 ? 'reference' : 'references'}`));
    const grouped = new Map();
    left.forEach((item) => {
      const why = item.why || 'could not be matched';
      grouped.set(why, (grouped.get(why) || []).concat(item.name));
    });
    grouped.forEach((names, why) => {
      const said = el('p', 'aud-unused-why');
      withTitles(said, `${nameList(names)} `
        + `${names.length === 1 ? 'was' : 'were'} ${why}.`, names);
      details.appendChild(said);
    });
    body.appendChild(details);
  }

  if (a.source === 'description' && a.text) {
    const show = el('button', 'linky', 'View source data');
    show.type = 'button';
    const text = el('p', 'aud-source');
    text.hidden = true;
    text.textContent = a.text;
    show.onclick = () => {
      text.hidden = !text.hidden;
      show.textContent = text.hidden ? 'View source data' : 'Hide';
    };
    body.append(show, text);
  }
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
  if (drawSpace.updateResetTooltip) drawSpace.updateResetTooltip();
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
          locked: locked(),
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