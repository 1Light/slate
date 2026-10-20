const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const grey = (i) => `var(--g${i % 6})`;

const seen = new WeakSet();
function onceVisible(node, fn, threshold = 0.2) {
  if (!('IntersectionObserver' in window)) { fn(); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting || seen.has(e.target)) return;
      seen.add(e.target);
      io.disconnect();
      fn();
    });
  }, { threshold });
  io.observe(node);
}

function markWhere() {
  const tabs = [...document.querySelectorAll('.tabs a')];
  const spots = tabs
    .map((tab) => ({ tab, at: document.querySelector(tab.getAttribute('href')) }))
    .filter((s) => s.at);
  if (!spots.length) return;

  const mark = () => {
    const line = window.scrollY + window.innerHeight * 0.3;
    const passed = spots
      .filter((s) => s.at.offsetParent !== null || s.at.offsetHeight)
      .map((s) => ({
        tab: s.tab,
        top: s.at.getBoundingClientRect().top + window.scrollY,
      }))
      .filter((s) => s.top > 0 && s.top <= line)
      .sort((a, b) => a.top - b.top);
    const live = passed.length ? passed[passed.length - 1].tab : null;
    tabs.forEach((tab) => tab.classList.toggle('here', tab === live));
  };

  mark();
  window.addEventListener('scroll', mark, { passive: true });
  window.addEventListener('resize', mark, { passive: true });
  new MutationObserver(mark).observe(document.body,
    { attributes: true, subtree: true, attributeFilter: ['hidden'] });
}

function backToTop() {
  const btn = $('to-top');
  if (!btn) return;
  const mark = () => { btn.hidden = window.scrollY < window.innerHeight * 0.8; };
  mark();
  window.addEventListener('scroll', mark, { passive: true });
  btn.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
}

function stickyBar() {
  const bar = $('bar');
  if (!bar) return;
  const mark = () => bar.classList.toggle('lifted', window.scrollY > 24);
  mark();
  window.addEventListener('scroll', mark, { passive: true });
}

function revealAll() {
  document.querySelectorAll('.reveal').forEach((n) => {
    onceVisible(n, () => n.classList.add('shown'), 0.08);
  });
}

async function ask(url, options) {
  const res = await fetch(url, options);
  let body = null;
  try { body = await res.json(); } catch {  }
  if (!res.ok) {
    const err = new Error((body && body.detail)
      || 'Qloo did not answer. Try again in a moment.');
    err.status = res.status;
    throw err;
  }
  return body;
}

function problem(message) {
  const box = $('error');
  if (!box) return;
  box.hidden = false;
  $('error-text').textContent = message;
}
const SPELL = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
  'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
  'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty',
  'twenty-one', 'twenty-two', 'twenty-three', 'twenty-four'];
const spell = (n) => SPELL[n] || String(n);
const Caps = (t) => t.charAt(0).toUpperCase() + t.slice(1);

const SHUFFLE = (i) => {
  const x = Math.sin(i * 73.7 + 5.3) * 4411.9;
  return x - Math.floor(x);
};

function cardStage(host, plan) {
  if (!host) return;
  const draw = () => {
    const room = host.clientWidth;
    if (!room) return;
    host.textContent = '';

    const { groups, card, step, loop, extra } = plan;
    const lanes = groups.length + (extra ? 1 : 0);
    const gap = card.w * 0.55;
    const wide = lanes * card.w + (lanes - 1) * gap;
    const left = Math.max(card.w * 0.3, (room - wide) / 2);
    const laneAt = (i) => left + i * (card.w + gap);

    const label = plan.notes ? 38 : 26;
    const deepest = Math.max(...groups.map((c) => (c - 1) * step + card.h + 16));
    const whole = label + deepest;
    const top = label + Math.max(8, (host.clientHeight - whole) / 2);

    host.style.setProperty('--loop', `${loop}s`);

    groups.forEach((count, g) => {
      const box = el('s');
      box.style.left = `${laneAt(g) - 6}px`;
      box.style.top = `${top}px`;
      box.style.width = `${card.w + 12}px`;
      box.style.height = `${(count - 1) * step + card.h + 16}px`;
      host.appendChild(box);

      const tag = el('span');
      tag.appendChild(el('u', null, 'ABCDEF'[g]));
      if (plan.notes) tag.appendChild(el('em', null, `${count} films`));
      tag.style.left = `${laneAt(g) - 6}px`;
      tag.style.top = `${top - label}px`;
      host.appendChild(tag);
    });

    const spots = [];
    groups.forEach((count, g) => {
      for (let k = 0; k < count; k += 1) {
        spots.push({ x: laneAt(g), y: top + 8 + k * step, z: k + 1 });
      }
    });
    if (extra === 'span') {
      spots.push({
        x: laneAt(0) + (card.w + gap) / 2 + (card.h - card.w) / 2,
        y: top + (card.h - card.w) / -2 + card.h * 1.25,
        z: 40, turn: 90, role: 'span',
      });
    } else if (extra === 'apart') {
      spots.push({
        x: laneAt(groups.length), y: top + card.h * 0.75, z: 40,
        turn: -9, role: 'apart',
      });
    }

    const from = { x: left + wide / 2 - card.w / 2, y: top + card.h * 0.4 };
    spots.forEach((spot, n) => {
      const node = el('i', spot.role || null);
      const sx = from.x + (SHUFFLE(n) - 0.5) * 10;
      const sy = from.y + (SHUFFLE(n + 30) - 0.5) * 10;
      node.style.left = `${sx}px`;
      node.style.top = `${sy}px`;
      node.style.setProperty('--r0', `${(SHUFFLE(n + 7) - 0.5) * 16}deg`);
      node.style.setProperty('--r1',
        `${spot.turn != null ? spot.turn : (SHUFFLE(n + 61) - 0.5) * 3}deg`);
      node.style.setProperty('--tx', `${spot.x - sx}px`);
      node.style.setProperty('--ty', `${spot.y - sy}px`);
      node.style.zIndex = String(spot.z);
      node.style.animationDelay = `${n * 0.055}s`;
      host.appendChild(node);
    });
  };

  draw();
  let waiting;
  window.addEventListener('resize', () => {
    clearTimeout(waiting);
    waiting = setTimeout(draw, 180);
  }, { passive: true });
}

function heroStage() {
  cardStage($('stage-hero'), {
    groups: [8, 6, 6],
    card: { w: 76, h: 104, pad: 14 },
    step: 23, loop: 10, notes: true,
  });
}

function markStage(id, kind) {
  cardStage($(id), {
    groups: [3, 3, 3],
    card: { w: 52, h: 72, pad: 10 },
    step: 15, loop: 8, extra: kind === 'bridge' ? 'span' : 'apart',
  });
}

async function start() {
  let list;
  try { list = await ask('/api/lineups'); } catch (e) { problem(e.message); return; }

  const host = $('chapters');
  const byslug = {};
  let n = 0;
  for (const item of list) {
    if (item.slug === 'one-genre') continue;
    let data;
    try { data = await ask(`/api/lineups/${item.slug}`); } catch { continue; }
    n += 1;
    const sec = chapter(data, item.slug, n);
    host.appendChild(sec);
    byslug[item.slug] = true;
    if (item.slug === 'sundance2024') {
      const hook = el('section', 'panel reveal');
      hook.id = 'panel';
      host.appendChild(hook);
      panel(hook, { slug: item.slug }, data.films.map((f) => f.title));
    }
  }
  if (!n) { problem('No programmes could be read.'); return; }

  agentSection();
  viewTabs();
  tests();
  revealAll();
  stickyBar();
  backToTop();
  markWhere();
  const ex = $('own-example');
  if (ex) ex.onclick = useExample;
  heroStage();
  markStage('stage-bridge', 'bridge');
  markStage('stage-outlier', 'outlier');
}

function chapter(d, slug, index) {
  const sec = el('section', 'chapter reveal');
  sec.dataset.slug = slug;

  const title = el('p', 'chapter-title');
  if (index) title.appendChild(el('span', 'num', String(index)));
  title.appendChild(el('span', 'where', (d.name || '').replace(/\s*\u2014\s*probe$/, '')));

  sec.appendChild(title);
  sec.appendChild(verdict(d));

  const fig = el('div', 'figure');
  const sizes = el('div', 'sizes');
  const cols = el('div', 'columns');
  const taken = el('div', 'taken');
  const spend = el('div', 'spend');
  const legend = el('div', 'legend');
  taken.hidden = true;
  fig.append(sizes, cols, taken, spend, legend);
  sec.appendChild(fig);

  board(d, { cols, spend, legend, sizes, taken });
  return sec;
}

function verdict(d) {
  const h = d.headline;
  const line = el('h2', 'verdict-line');
  const put = (t) => line.appendChild(document.createTextNode(t));
  const num = (n) => line.appendChild(el('b', null, String(n)));

  num(h.films); put(` ${d.nouns || 'items'}`);
  if (h.origins > 1) { put(' from '); num(h.origins); put(' countries'); }
  put(' reach '); num(h.clusters);
  put(h.clusters === 1 ? ' audience.' : ' audiences.');
  return line;
}

function filmNode(f, fresh) {
  const n = el('span', 'film');
  n.dataset.title = f.title;
  n.appendChild(document.createTextNode(f.title));
  if (f.year) n.appendChild(el('span', 'year', String(f.year)));
  if (f.origin) n.appendChild(el('span', 'origin', f.origin));
  if (fresh && fresh.has(f.title)) {
    n.classList.add('arriving');
    n.appendChild(el('span', 'tag', 'added'));
  }
  if (f.role === 'bridge') {
    n.classList.add('bridge');
    n.appendChild(el('span', 'tag', 'bridge'));
  }
  if (f.role === 'alone') {
    n.classList.add('alone');
    n.appendChild(el('span', 'tag', 'outlier'));
  }
  if (f.coverage < 0.5) {
    n.classList.add('thin');
    n.title = `Returned by ${Math.round(f.coverage * 100)} per cent of the other `
            + 'films, so its position is the least certain here.';
  }
  return n;
}

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const letterFor = (i) => LETTERS[i] || String(i + 1);

function columnHead(count, index, noun, nouns) {
  const h = el('div', 'column-head');
  if (index != null) h.appendChild(el('span', 'column-letter', letterFor(index)));
  h.appendChild(el('span', 'column-size', String(count)));
  h.appendChild(document.createTextNode(' '));
  h.appendChild(el('span', 'column-what',
    count === 1 ? `${noun || 'film'} · its own audience group`
                : `${nouns || 'films'} · one audience group`));
  return h;
}

function board(d, ui) {
  const { cols, spend, legend } = ui;
  const byTitle = Object.fromEntries(d.films.map((f) => [f.title, f]));
  const nodes = new Map();

  const weight = (n) => `${n} 1 0`;

  const spendBand = () => {
    spend.textContent = '';
    const usable = d.clusters.filter((c) => c.films.length >= 3
      && d.tightest.some((t) => t.cluster === c.index));
    if (!usable.length) return;

    const head = el('div', 'spend-head');
    head.appendChild(el('h4', null, 'If you need to free a slot'));
    head.appendChild(el('p', null,
      'These pairs overlap more than any others in their group. Drop either '
      + 'one and the group still covers its audience.'));
    spend.appendChild(head);

    const rows = el('ul', 'spend-rows');
    d.clusters.forEach((c, i) => {
      if (c.films.length < 3) return;
      const pairs = d.tightest.filter((t) => t.cluster === c.index).slice(0, 3);
      pairs.forEach((t) => {
        const li = el('li');
        li.appendChild(el('span', 'spend-letter', letterFor(i)));
        li.appendChild(document.createTextNode(`${t.a} or ${t.b}`));
        rows.appendChild(li);
      });
    });
    spend.appendChild(rows);
  };

  const settle = () => {
    cols.textContent = '';
    d.clusters.forEach((c, i) => {
      const col = el('div', 'column');
      col.appendChild(columnHead(c.films.length, i, d.noun, d.nouns));
      c.films.slice()
        .sort((a, b) => byTitle[b].isolation - byTitle[a].isolation)
        .forEach((t) => col.appendChild(nodes.get(t) || filmNode(byTitle[t], fresh)));
      cols.appendChild(col);
    });
    spendBand();
    if (ui.sizes) {
      ui.sizes.textContent = '';
      d.clusters.forEach((c) => {
        const bar = el('span');
        bar.style.flex = String(c.films.length);
        ui.sizes.appendChild(bar);
      });
    }
    if (ui.taken) {
      ui.taken.textContent = '';
      const yours = d.by_you || [];
      ui.taken.hidden = !yours.length;
      if (yours.length) {
        ui.taken.appendChild(el('span', 'taken-head', 'Removed'));
        const list = el('div', 'taken-list');
        yours.forEach((t) => {
          const back = el('button', 'taken-film');
          back.type = 'button';
          back.title = 'Put it back';
          back.textContent = t;
          if (ui.onPutBack) back.onclick = () => ui.onPutBack(t);
          list.appendChild(back);
        });
        ui.taken.appendChild(list);
      }
    }
    legendText(d, legend);
  };

  if (reduced) {
    settle();
    if (ui.onSettle) ui.onSettle();
    return;
  }

  const fresh = new Set(d.added || []);
  const first = el('div', 'column');
  const head = el('div', 'column-head');
  head.appendChild(el('span', 'column-size', String(d.films.length)));
  head.appendChild(document.createTextNode(' '));
  head.appendChild(el('span', 'column-what', 'films · as the festival lists them'));
  first.appendChild(head);
  [...d.films].sort((a, b) => a.title.localeCompare(b.title)).forEach((f) => {
    const n = filmNode(f, fresh);
    nodes.set(f.title, n);
    first.appendChild(n);
  });
  cols.appendChild(first);

  onceVisible(cols, () => {
    const before = new Map();
    nodes.forEach((n, t) => before.set(t, n.getBoundingClientRect()));
    settle();

    const moving = [];
    nodes.forEach((n, t) => {
      const a = before.get(t);
      const b = n.getBoundingClientRect();
      if (!a) return;
      const dx = a.left - b.left;
      const dy = a.top - b.top;
      if (!dx && !dy) return;
      moving.push(n.animate(
        [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }],
        { duration: 780, easing: 'cubic-bezier(.22,.9,.3,1)', fill: 'both' },
      ));
    });
    const done = () => { if (ui.onSettle) ui.onSettle(); };
    Promise.all(moving.map((a) => a.finished)).then(done).catch(done);
  }, 0.15);
}

function nameList(items) {
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

function legendText(d, node) {
  node.textContent = '';
  const line = (text) => node.appendChild(el('p', null, text));

  const bridges = (d.bridges || []).map((b) => b.film);
  if (bridges.length === 1) {
    const b = d.bridges[0];
    const n = b.connects.length;
    line(n >= d.clusters.length
      ? `${b.film} is a bridge. It links all ${n} groups.`
      : `${b.film} is a bridge. It links ${n} of the ${d.clusters.length} groups.`);
  } else if (bridges.length > 1) {
    line(`${nameList(bridges)} are bridges. Each links groups that would `
      + 'otherwise be separate.');
  }

  const alone = d.films.filter((f) => f.role === 'alone').map((f) => f.title);
  if (alone.length === 1) {
    line(`${alone[0]} is an outlier. It is weakly tied to its group and `
      + 'covers taste nothing else here covers.');
  } else if (alone.length > 1) {
    line(`${nameList(alone)} are outliers. Each is weakly tied to its group `
      + 'and covers taste nothing else here covers.');
  }

  const gone = (d.excluded || []).concat(d.unresolved || []);
  if (gone.length === 1) {
    line(`${gone[0]} is in this lineup but Qloo has no affinity data linking `
      + 'it to the others, so it is not shown.');
  } else if (gone.length > 1) {
    line(`${nameList(gone)} are in this lineup but Qloo has no affinity data `
      + 'linking them to the others, so they are not shown.');
  }
}

function controlFigure(d, host) {
  host.textContent = '';
  const cols = el('div', 'columns tight');
  d.clusters.slice().sort((a, b) => b.films.length - a.films.length)
    .forEach((c, i) => {
      const col = el('div', 'column');
      col.appendChild(columnHead(c.films.length, i, d.noun, d.nouns));
      c.films.slice().sort().forEach((t) => {
        const row = el('span', 'film');
        row.appendChild(document.createTextNode(t));
        col.appendChild(row);
      });
      cols.appendChild(col);
    });
  host.appendChild(cols);
}

function titled(label, node) {
  const wrap = el('div', 'figure-block');
  if (label) wrap.appendChild(el('p', 'figure-label', label));
  wrap.appendChild(node);
  return wrap;
}

function mlTables(ml, which) {
  if (which === 'baselines') {
    const bt = el('table', 'bars-table');
    const widest = Math.max(...ml.baselines.map((x) => Math.abs(x.rho)));
    ml.baselines.forEach((x, i) => {
      const tr = el('tr', i === 0 ? 'win' : null);
      tr.appendChild(el('td', 'who', x.name));
      tr.appendChild(el('td', 'd', `${x.rho >= 0 ? '+' : ''}${x.rho.toFixed(3)}`));
      const cell = el('td', 'bar');
      const fill = el('span');
      fill.style.width = `${(Math.abs(x.rho) / widest) * 100}%`;
      cell.appendChild(fill);
      tr.appendChild(cell);
      bt.appendChild(tr);
    });
    return bt;
  }
  const t = el('table', 'pairs');
  const headRow = () => {
    const tr = el('tr', 'head');
    ['Distance', 'Pair', 'Agreement', 'Rated both'].forEach((label, i) => {
      tr.appendChild(el('td', i === 0 ? 'd' : i === 1 ? '' : 'r', label));
    });
    t.appendChild(tr);
  };
  const band = (label) => {
    const tr = el('tr', 'band');
    const td = el('td', null, label);
    td.colSpan = 4;
    tr.appendChild(td);
    t.appendChild(tr);
  };
  const row = (p) => {
    const tr = el('tr');
    tr.appendChild(el('td', 'd', p.distance.toFixed(2)));
    tr.appendChild(el('td', 'pair', `${p.a} / ${p.b}`));
    tr.appendChild(el('td', 'r strong', p.r.toFixed(2)));
    tr.appendChild(el('td', 'n', p.n.toLocaleString()));
    t.appendChild(tr);
  };
  headRow();
  band('Closest by Slate');
  ml.closest.forEach(row);
  band('Furthest by Slate');
  ml.furthest.forEach(row);
  return t;
}

function stabilityTable(st) {
  const t = el('table', 'bars-table');
  const head = el('tr', 'head');
  ['Group', 'Held', 'By chance', 'The gap'].forEach((label, i) => {
    head.appendChild(el('td', i === 0 ? 'who' : 'd', label));
  });
  t.appendChild(head);
  const scored = st.clusters.filter((c) => c.lift != null);
  const widest = Math.max(...scored.map((c) => c.lift), 0.01);
  scored.forEach((c) => {
    const tr = el('tr', 'win');
    tr.appendChild(el('td', 'who', `${c.size} films`));
    tr.appendChild(el('td', 'd', c.jaccard.toFixed(2)));
    tr.appendChild(el('td', 'd', c.chance.toFixed(2)));
    const cell = el('td', 'bar');
    const fill = el('span');
    fill.style.width = `${(c.lift / widest) * 100}%`;
    cell.appendChild(fill);
    tr.appendChild(cell);
    t.appendChild(tr);
  });
  return t;
}

function bridgeTable(b) {
  const t = el('table', 'bars-table');
  b.rows.forEach((r) => {
    const tr = el('tr');
    tr.appendChild(el('td', 'who', r.lineup));
    tr.appendChild(el('td', 'd', `${r.rho >= 0 ? '+' : ''}${r.rho.toFixed(2)}`));
    t.appendChild(tr);
  });
  const tr = el('tr', 'win');
  tr.appendChild(el('td', 'who', `All ${b.films} films`));
  tr.appendChild(el('td', 'd',
    `${b.pooled_rho >= 0 ? '+' : ''}${b.pooled_rho.toFixed(2)}`));
  t.appendChild(tr);
  return t;
}

async function tests() {
  let v = null;
  try { v = await ask('/api/validation'); } catch {  }
  let control = null;
  try { control = await ask('/api/lineups/one-genre'); } catch {  }

  const host = $('tests');
  if (!host) return;
  host.textContent = '';

  let built = 0;
  const test = (n, question) => {
    built += 1;
    const art = el('article', 'test');
    const h = el('h3');
    h.appendChild(el('span', 'num', String(n)));
    h.appendChild(document.createTextNode(question));
    art.appendChild(h);
    host.appendChild(art);
    art.rail = art;
    art.aside = art;
    art.after = art;
    return art;
  };

  const say = (art, text, cls) =>
    (art.rail || art).appendChild(el('p', cls || null, text));
  const below = (art, text, cls) =>
    (art.after || art).appendChild(el('p', cls || null, text));

  try {
    if (control) {
    const art = test(1, 'Does Slate just group by genre?');
    say(art, `${Caps(spell(control.films.length))} science fiction films were `
      + 'given to Slate as one lineup. Every one of them carries the same '
      + 'genre tag. If Slate were grouping by genre, they would all come back '
      + 'as one audience.');
    const fig = el('div', 'control-figure');
    controlFigure(control, fig);
    art.appendChild(fig);
    below(art, `They come back as ${spell(control.clusters.length)}. So Slate `
      + 'is not grouping by genre: it is reading something the genre tag does '
      + 'not contain.', 'closing-line');
  }

  if (v && v.movielens) {
    const ml = v.movielens;
    const art = test(2, 'Do the groups match how people actually behave?');
    say(art, 'Everything above comes from Qloo. To check it against something '
      + 'else, Slate used MovieLens: 32 million film ratings published by a '
      + 'research group at the University of Minnesota, with no connection to '
      + 'Qloo.');
    say(art, 'Slate\u2019s distance between two films is built from Qloo\u2019s '
      + 'rankings: ask Qloo about each film, see where it places the others, '
      + 'average the two directions.');
    say(art, 'For each pair in the science fiction lineup, Slate then found '
      + 'every MovieLens user who had rated both films and measured how '
      + 'closely their two sets of scores moved together (Pearson).');
    art.appendChild(titled(null, mlTables(ml, 'pairs')));
    below(art, 'The further apart Slate places two films, the less the people '
      + `who saw both agreed about them. Across all ${ml.pairs} pairs, that `
      + `relationship measures ${ml.rho.toFixed(3)} (Spearman). This is shown `
      + 'in a dataset Qloo never touched.');
    below(art, 'Hence the groups Slate makes match how people actually behave.',
      'closing-line');

    const art2 = test('2b', 'Could metadata make the same groups Slate does?');
    art2.classList.add('sub');
    say(art2, 'Genre, release year and popularity are free: anyone has them '
      + 'without an API. If one of them explained agreement as well as '
      + 'Slate\u2019s distance does, Slate would not be needed.');
    say(art2, `Every pair of films in the lineup, ${ml.pairs} of them, was `
      + 'tested again against the same MovieLens agreement numbers, using a '
      + 'different measure of closeness each time:');
    const ul = el('ul', 'defs');
    [['Slate distance', 'how far apart Slate places the two films'],
     ['Years apart', 'the gap between their release years'],
     ['Popularity gap', 'the difference in how well known they are'],
     ['Shared genres', 'how many genre tags the two films have in common']]
      .forEach(([k, t]) => {
        const li = el('li');
        li.appendChild(el('b', null, k));
        li.appendChild(document.createTextNode(`: ${t}`));
        ul.appendChild(li);
      });
    art2.rail.appendChild(ul);
    say(art2, 'Genre and release year come from MovieLens itself. Popularity '
      + 'comes from Qloo.');
    say(art2, 'For each measure, Slate correlated it against the agreement '
      + `numbers across all ${ml.pairs} pairs. A number near zero means that `
      + 'measure tells you nothing about whether two films\u2019 viewers '
      + 'agreed. The further from zero, the more it tells you.');
    art2.appendChild(titled('Correlated against the same agreement numbers',
      mlTables(ml, 'baselines')));
    below(art2, `Next to Slate\u2019s ${ml.rho.toFixed(3)}, the other three `
      + 'sit near zero. Slate\u2019s distance tells you far more about whether '
      + 'two films\u2019 viewers agreed than any of them.');
    below(art2, 'Hence metadata cannot make these groups. Slate is reading '
      + 'something it does not contain.', 'closing-line');
  }

  if (control && control.stability) {
    const st = control.stability;
    const art = test(3, 'How sensitive are the groups to the lineup itself?');
    say(art, 'If a group only exists because one particular film happens to '
      + 'be in the lineup, it is not telling you anything. So Slate removes '
      + 'each film in turn and redoes the whole analysis: re-ranks the '
      + 'remaining films against each other, rebuilds the distances, and lets '
      + 'the engine choose how many groups it wants from scratch. Then it '
      + 'compares the result against the original.');
    say(art, 'If the groups are real, every remaining film should land back '
      + 'in the same group it was in before.');
    say(art, 'The comparison is scored with the adjusted Rand index, a '
      + 'standard measure of how closely two groupings agree (the new '
      + 'grouping against the original). It runs from 0 to 1. A score of 1.00 '
      + 'means identical, above 0.8 means largely intact, and 0.6 to 0.8 '
      + 'means mostly intact with some films moving.');
    if (v && v.lineup_ari) {
      art.appendChild(titled('Adjusted Rand index, by lineup',
        ariTable(v.lineup_ari)));
    }
    say(art, 'Each group is also checked on its own with Jaccard: of the '
      + 'films that were in that group, how many are still together '
      + 'afterwards.');
    say(art, 'Slate shuffles every film\u2019s ranking so the order carries no '
      + 'information, then runs the same test again. Each run removes one '
      + 'film and re-clusters, and for each group counts how many of its '
      + 'films are still together: two of two is 1.00, three of four is 0.75. '
      + 'The scores are averaged over all the runs.');
    art.appendChild(titled('Each group on its own, science fiction lineup',
      stabilityTable(st)));
    below(art, 'The effect is most visible on small groups. If a group has '
      + 'only two films and you remove one, the pair is gone, so Jaccard '
      + 'always scores it badly however real it was. On shuffled rankings a '
      + 'pair gets about 0.44. A real pair scoring 0.69 is above that, and '
      + 'the gap is what counts.');
    below(art, 'Hence, based on the results shown, the groups do not depend '
      + 'on any one film being in the lineup.', 'closing-line');
  }

  if (v && v.bridge && v.bridge.rows && v.bridge.rows.length) {
    const b = v.bridge;
    const art = test(4, 'Is a bridge just the most popular film?');
    say(art, 'A well known film sits near more things, so it could land '
      + 'between groups for the wrong reason. If that were happening, Slate '
      + 'would be labelling fame as connection.');
    say(art, 'To check, Slate takes every film in a lineup and compares two '
      + 'numbers:');
    const ul = el('ul', 'defs');
    [['Betweenness', 'how many of the shortest routes between films pass '
      + 'through it, computed with Brandes\u2019 algorithm. This is what makes '
      + 'a film a bridge'],
     ['Popularity', 'Qloo\u2019s own measure of how well known it is, from 0 '
      + 'to 1']].forEach(([k, t]) => {
      const li = el('li');
      li.appendChild(el('b', null, k));
      li.appendChild(document.createTextNode(`: ${t}`));
      ul.appendChild(li);
    });
    art.rail.appendChild(ul);
    say(art, 'If betweenness is really popularity in disguise, the two should '
      + 'rise and fall together in every lineup. Each number below is the '
      + 'correlation between them across all the films in that lineup '
      + '(Spearman):');
    art.appendChild(titled('Betweenness against popularity, by lineup',
      bridgeTable(b)));
    below(art, 'They do not. Two lineups go one way, two the other, and '
      + `across all ${b.films} films the relationship is nothing. In the `
      + 'science fiction lineup it runs strongly negative, which means the '
      + 'least popular films carry the most routes.');
    below(art, 'High betweenness alone is not enough to be called a bridge. '
      + 'Slate builds the graph three times, connecting each film to its 2, 3 '
      + 'and 4 nearest, and a film only qualifies if it stays in the top '
      + 'three every time. A film that leads on one setting and falls away on '
      + 'another was never a connector.');
    if (b.caught) {
      const p = el('p');
      p.appendChild(document.createTextNode(
        'The clearest case is Sundance. The film with the most routes through '
        + 'it is '));
      p.appendChild(el('i', null, b.caught.top_by_betweenness));
      p.appendChild(document.createTextNode(
        ', the most popular film in that lineup. Slate did not call it a '
        + 'bridge: it did not rank in the top three for betweenness across '
        + 'all of the 2, 3 and 4 nearest settings. '));
      p.appendChild(el('i', null, b.caught.bridges[0]));
      p.appendChild(document.createTextNode(' did, and was named instead.'));
      art.after.appendChild(p);
    }
    below(art, 'Hence a bridge is not the most popular film wearing a label.',
      'closing-line');
  }

  } catch (e) {
    console.error('evidence section', e);
  }

  if (built) show($('checked'));
}

function show(sec) {
  if (!sec) return;
  sec.hidden = false;
  onceVisible(sec, () => sec.classList.add('shown'), 0.05);
}

function ariTable(rows) {
  const t = el('table', 'bars-table');
  rows.forEach((r) => {
    const tr = el('tr', 'win');
    tr.appendChild(el('td', 'who', r.name));
    tr.appendChild(el('td', 'd', `+${r.ari.toFixed(2)}`));
    t.appendChild(tr);
  });
  return t;
}

function settleInto(fig, before, moved) {
  if (!before.size || reduced) return;
  const mark = new Set(moved);
  fig.querySelectorAll('.film[data-title]').forEach((row) => {
    const was = before.get(row.dataset.title);
    if (!was) {
      row.animate([{ opacity: 0 }, { opacity: 1 }],
        { duration: 420, delay: 180, easing: 'ease-out', fill: 'both' });
      return;
    }
    const now = row.getBoundingClientRect();
    const dx = was.left - now.left;
    const dy = was.top - now.top;
    if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return;
    row.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` },
       { transform: 'none' }],
      { duration: mark.has(row.dataset.title) ? 640 : 460,
        easing: 'cubic-bezier(.3,.9,.3,1)', fill: 'both' });
  });
}

function panel(host, source, baseFilms) {
  const state = { drop: [], add: [], keep: null, films: baseFilms.slice() };
  host.textContent = '';

  const box = el('div', 'panel-box');
  box.appendChild(el('h3', null, 'Analyse the lineup'));
  box.appendChild(el('p', 'lede',
    'Take films out, or put one in. The groups are worked out again each time.'));
  const chips = el('div', 'chips');
  box.appendChild(chips);

  const row = el('div', 'row');
  const field = el('input');
  field.type = 'text';
  field.placeholder = 'Add a film by title';
  const addBtn = el('button', 'ghost', 'Add');
  addBtn.type = 'button';
  row.append(field, addBtn);
  box.appendChild(row);
  host.appendChild(box);

  const say = el('div', 'panel-diff');
  const fig = el('div', 'panel-figure');
  const foot = el('p', 'panel-foot');
  say.hidden = true;
  host.append(say, fig, foot);

  const fewer = el('div', 'panel-fewer');
  fewer.hidden = true;

  const ask_agent = el('div', 'panel-fewer panel-swap');
  ask_agent.hidden = true;
  ask_agent.appendChild(el('h3', null, 'Swap a film to reach more audiences'));
  ask_agent.appendChild(el('p', 'lede',
    'Slate drops a slot the lineup can spare and brings in something from '
    + 'outside your list.'));
  const swapRowEl = el('div', 'row');
  const swapBtn = el('button', 'ghost', 'Suggest a swap');
  swapBtn.type = 'button';
  const swapSaid = el('span', 'fine');
  swapRowEl.append(swapBtn, swapSaid);
  ask_agent.appendChild(swapRowEl);
  fewer.appendChild(el('h3', null, 'Fit it into fewer slots'));
  fewer.appendChild(el('p', 'lede',
    'If you only have room for some of these, Slate picks the set that '
    + 'reaches the most separate audiences.'));
  const frow = el('div', 'row');
  frow.appendChild(el('span', 'fine', 'Keep'));
  const pick = el('select');
  const count = el('span', 'fine');
  const findBtn = el('button', 'ghost', 'Find the best set');
  findBtn.type = 'button';
  frow.append(pick, count, findBtn);
  fewer.appendChild(frow);
  host.appendChild(fewer);
  host.appendChild(ask_agent);

  const drawChips = () => {
    chips.textContent = '';
    state.films.filter((t) => !state.drop.includes(t)).forEach((t) => {
      const chip = el('button', 'chip');
      chip.type = 'button';
      chip.appendChild(document.createTextNode(t));
      chip.appendChild(el('span', 'chip-x', '\u00d7'));
      chip.onclick = () => {
        state.drop = state.drop.concat(t);
        state.keep = null;
        drawChips();
        drawSizes();
        run();
      };
      chips.appendChild(chip);
    });
  };

  const putBack = (title) => {
    state.drop = state.drop.filter((x) => x !== title);
    state.keep = null;
    drawChips();
    drawSizes();
    run();
  };

  const drawSizes = () => {
    const n = state.films.filter((t) => !state.drop.includes(t)).length;
    const was = pick.value;
    pick.textContent = '';
    for (let k = n - 1; k >= 4; k -= 1) {
      pick.appendChild(el('option', null, String(k)));
    }
    if (was && Number(was) < n) pick.value = was;
    count.textContent = `of the ${n}`;
    findBtn.disabled = n <= 4;
  };

  const run = async (opts) => {
    const wantSwap = !!(opts && opts.swap);
    say.textContent = '';
    say.appendChild(el('p', null, 'Working it out'));
    say.hidden = false;
    fig.textContent = '';
    try {
      const body = { drop: state.drop, add: state.add };
      if (source.slug) body.slug = source.slug;
      else body.films = source.films;
      if (state.keep) body.keep = state.keep;
      if (wantSwap) body.swap = true;

      const d = await ask('/api/panel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      say.textContent = '';
      ((d.diff && d.diff.line) || '').split('. ').filter(Boolean)
        .forEach((part, i, all) => {
          const dot = part.endsWith('.') ? '' : '.';
          say.appendChild(el('p', null, part + (i === all.length - 1 ? dot : '.')));
        });
      fewer.hidden = false;
      ask_agent.hidden = false;

      const before = new Map();
      fig.querySelectorAll('.film[data-title]').forEach((row) => {
        before.set(row.dataset.title, row.getBoundingClientRect());
      });
      fig.textContent = '';
      const sec = chapter(d, null);
      sec.classList.add('shown');
      const head = sec.querySelector('.chapter-title');
      if (head) head.remove();
      const vline = sec.querySelector('.verdict-line');
      if (vline) vline.remove();
      const spend = sec.querySelector('.spend');
      if (spend) spend.remove();
      fig.appendChild(sec);
      settleInto(fig, before, (d.diff && d.diff.moved) || []);

      const back = sec.querySelectorAll('.taken-film');
      back.forEach((b) => { b.onclick = () => putBack(b.textContent); });

      foot.textContent = '';
      const mine = new Set(d.by_you || []);
      const theirs = (d.dropped || []).filter((t) => !mine.has(t));
      if (theirs.length) {
        foot.appendChild(el('p', null, `Slate dropped: ${theirs.join(', ')}.`));
      }
      if (state.drop.length || state.add.length || state.keep) {
        const reset = el('button', 'ghost', 'Reset to the real lineup');
        reset.type = 'button';
        reset.onclick = () => {
          state.drop = []; state.add = []; state.keep = null;
          state.films = baseFilms.slice();
          drawChips(); drawSizes(); run();
        };
        foot.appendChild(reset);
      }
      drawSizes();

      swapSaid.textContent = '';
      if (d.agent) {
        swapSaid.textContent = d.agent.swaps.length
          ? `${d.agent.swaps[0].out} out, ${d.agent.swaps[0].in} in.`
          : 'Nothing worth changing. Every candidate landed in a group the '
            + 'lineup already covers.';
        if (d.agent.swaps.length) {
          state.films = d.films.map((f) => f.title);
          state.drop = [];
          state.add = [];
          drawChips();
        }
      }
    } catch (e) {
      say.textContent = '';
      fig.textContent = '';
      failure(e, fig, run);
    }
  };

  addBtn.onclick = () => {
    const t = field.value.trim();
    if (!t) return;
    const here = state.films.some((f) => f.toLowerCase() === t.toLowerCase());
    if (here) {
      say.textContent = '';
      say.appendChild(el('p', null, `${t} is already in the lineup.`));
      say.hidden = false;
      return;
    }
    state.add = state.add.concat(t);
    state.films = state.films.concat(t);
    state.keep = null;
    field.value = '';
    drawChips();
    run();
  };
  field.onkeydown = (ev) => { if (ev.key === 'Enter') addBtn.onclick(); };
  findBtn.onclick = () => { state.keep = Number(pick.value); run(); };
  swapBtn.onclick = async () => {
    swapBtn.disabled = true;
    swapBtn.textContent = 'Testing candidates';
    swapSaid.textContent = '';
    try {
      await run({ swap: true });
    } finally {
      swapBtn.disabled = false;
      swapBtn.textContent = 'Suggest a swap';
    }
  };

  drawChips();
  drawSizes();
}

function swapRow(sw) {
  const li = el('li');
  li.appendChild(el('span', 'out', sw.out));
  li.appendChild(el('span', 'arrow', '\u2192'));
  li.appendChild(el('span', 'in', sw.in + (sw.year ? ` (${sw.year})` : '')));
  if (sw.reason) li.appendChild(el('p', 'why', sw.reason));
  return li;
}

function agentCase(host, name, agent) {
  const box = el('article', 'agent-case');
  box.appendChild(el('p', 'agent-where', name));

  if (agent.swaps.length) {
    const first = agent.swaps[0];
    const last = agent.swaps[agent.swaps.length - 1];
    const shape = el('p', 'agent-shape');
    shape.appendChild(el('b', null, String(first.before.clusters)));
    shape.appendChild(document.createTextNode(' audiences becomes '));
    shape.appendChild(el('b', null, String(last.after.clusters)));
    shape.appendChild(document.createTextNode('. The largest group drops from '));
    shape.appendChild(el('b', null, String(first.before.largest_cluster)));
    shape.appendChild(document.createTextNode(' to '));
    shape.appendChild(el('b', null, String(last.after.largest_cluster)));
    shape.appendChild(document.createTextNode('.'));
    box.appendChild(shape);

    const list = el('ul', 'swaps');
    agent.swaps.forEach((sw) => list.appendChild(swapRow(sw)));
    box.appendChild(list);
  } else {
    box.appendChild(el('p', 'agent-shape', 'Nothing was changed.'));
    box.appendChild(el('p', 'why',
      'Each candidate was added, the whole set re-clustered, and the result '
      + 'measured. None reached an audience the lineup was missing.'));
    if (agent.rejected && agent.rejected.length) {
      box.appendChild(el('p', 'rejects-head', 'Tested and turned down'));
      const ul = el('ul', 'rejects');
      agent.rejected.slice(0, 4).forEach((r) => {
        const li = el('li');
        li.appendChild(el('span', 'out', r.film));
        li.appendChild(document.createTextNode(` \u2014 ${r.why}`));
        ul.appendChild(li);
      });
      box.appendChild(ul);
    }
  }
  host.appendChild(box);
}

async function agentSection() {
  const host = $('agent-body');
  if (!host) return;
  const want = [['cannes2023', 'Cannes 2023'],
                ['one-genre', 'A science fiction season']];
  let built = 0;
  for (const [slug, name] of want) {
    try {
      const r = await ask('/api/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      });
      agentCase(host, name, r.agent);
      built += 1;
    } catch (e) {
      console.error('agent case', slug, e);
    }
  }
  if (built) show($('agent'));
}

async function viewTabs() {
  let list;
  try { list = await ask('/api/views'); } catch { return; }
  if (!list || !list.length) return;

  const tabs = $('view-tabs');
  const body = $('view-body');
  tabs.textContent = '';
  const cache = {};

  const show = async (item, btn) => {
    [...tabs.children].forEach((b) => b.setAttribute('aria-selected',
      String(b === btn)));
    body.textContent = '';
    if (!cache[item.slug]) {
      try { cache[item.slug] = await ask(`/api/lineups/${item.slug}`); }
      catch { return; }
    }
    body.appendChild(chapter(cache[item.slug], item.slug));
    body.firstChild.classList.add('shown');
  };

  list.forEach((item, i) => {
    const btn = el('button', null, item.label);
    btn.type = 'button';
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', String(i === 0));
    btn.onclick = () => show(item, btn);
    tabs.appendChild(btn);
    if (i === 0) show(item, btn);
  });

  const sec = $('views');
  sec.hidden = false;
  onceVisible(sec, () => sec.classList.add('shown'), 0.05);
}

function status(kind, title, body, actions) {
  const box = el('div', `status ${kind}`);
  box.appendChild(el('h4', null, title));
  box.appendChild(el('p', null, body));
  if (actions && actions.length) {
    const row = el('div', 'row');
    actions.forEach(([label, fn, strong]) => {
      const b = el('button', strong ? 'solid' : 'ghost', label);
      b.type = 'button';
      b.onclick = fn;
      row.appendChild(b);
    });
    box.appendChild(row);
  }
  return box;
}

function coverage(d, host) {
  const gone = (d.unresolved || []).length + (d.excluded || []).length;
  if (!gone) return;
  const used = d.films.length;
  const nouns = d.nouns || 'titles';
  const hint = (d.entity_type === 'urn:entity:movie'
                || d.entity_type === 'urn:entity:tv_show')
    ? ' A year in brackets often fixes it, like Monster (2023).' : '';

  const box = el('div', 'coverage');
  box.appendChild(el('h4', null,
    `Analysed ${used} of the ${used + gone} ${nouns} you gave.`));

  if (d.unresolved && d.unresolved.length) {
    const p = el('p');
    p.appendChild(el('b', null, 'Not recognised: '));
    p.appendChild(document.createTextNode(
      `${nameList(d.unresolved)}.${hint}`));
    box.appendChild(p);
  }
  if (d.excluded && d.excluded.length) {
    const p = el('p');
    p.appendChild(el('b', null, 'Left out: '));
    p.appendChild(document.createTextNode(`${nameList(d.excluded)}. These `
      + `${nouns} are in Qloo\u2019s data, but it holds no taste connection `
      + 'between them and the rest of your list, so there was nothing to '
      + 'measure.'));
    box.appendChild(p);
  }
  host.appendChild(box);
}

function failure(err, out, retry) {
  const code = err && err.status;
  if (code === 429) {
    out.appendChild(status('wait', 'Qloo is limiting requests.',
      'Slate has stopped rather than sending more. Your lineup is still here '
      + 'and can be tried again shortly.',
      [['Try again', retry, true]]));
    return;
  }
  if (code === 503 || code === 502 || code === 504) {
    out.appendChild(status('broken', 'Slate couldn\u2019t finish this analysis.',
      'Qloo\u2019s data couldn\u2019t be retrieved, so there is no complete '
      + 'result to show. Nothing partial is displayed, because a half-read '
      + 'slate would look like a finding.',
      [['Try again', retry, true],
       ['See a measured lineup', () => { location.hash = '#cannes'; }]]));
    return;
  }
  out.appendChild(status('thin', 'This lineup can\u2019t be read.',
    (err && err.message) || 'Something in the submitted list stopped the '
    + 'analysis before it could finish.',
    [['Try again', retry]]));
}

const EXAMPLES = ['horror', 'jazz', 'sf-books', 'talk-podcasts', 'comedy-tv'];
let lastExample = null;

async function useExample() {
  const box = $('own-input');
  if (!box) return;
  const pool = EXAMPLES.filter((n) => n !== lastExample);
  const pick = pool[Math.floor(Math.random() * pool.length)];
  lastExample = pick;
  try {
    const d = await ask(`/api/examples/${pick}`);
    box.value = d.titles.join('\n');
    box.dataset.entityType = d.entity_type;
  } catch {  }
}

async function runOwn() {
  const raw = $('own-input').value.split('\n').map((s) => s.trim()).filter(Boolean);
  const out = $('own-result');
  const btn = $('own-run');
  out.textContent = '';

  if (raw.length < 4) {
    out.appendChild(status('thin', 'Add at least four titles.',
      `Slate needs four to read a shape. You have ${raw.length}.`, []));
    return;
  }
  if (raw.length > 24) {
    out.appendChild(status('thin', 'That is more than twenty-four.',
      `You have ${raw.length}. Remove a few and try again.`, []));
    return;
  }
  const films = raw;

  btn.disabled = true;
  btn.textContent = 'Reading';
  const waiting = el('div', 'waiting');
  waiting.appendChild(el('span', 'pulse'));
  const said = el('p', null, 'Looking up your titles');
  waiting.appendChild(said);
  out.appendChild(waiting);

  const stages = [
    [4000, 'Working out how they relate'],
    [11000, 'Working out the groups'],
    [18000, 'This is a new lineup, so it takes a little longer'],
  ].map(([at, text]) => setTimeout(() => { said.textContent = text; }, at));

  const box = $('own-input');
  const body = { films, name: 'Your slate' };
  if (box && box.dataset.entityType) body.entity_type = box.dataset.entityType;

  try {
    const d = await ask('/api/analyse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    stages.forEach(clearTimeout);
    out.textContent = '';
    coverage(d, out);
    const sec = chapter(d, null);
    sec.classList.add('shown');
    out.appendChild(sec);
    const hook = el('div', 'panel');
    out.appendChild(hook);
    panel(hook, { films }, d.films.map((f) => f.title));
    sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    stages.forEach(clearTimeout);
    out.textContent = '';
    failure(e, out, runOwn);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Find the shape';
  }
}

$('own-run').onclick = runOwn;

start();
