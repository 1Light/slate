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
  $('loading').hidden = true;
  $('error').hidden = false;
  $('error-text').textContent = message;
}
const SPELL = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
  'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
  'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty',
  'twenty-one', 'twenty-two', 'twenty-three', 'twenty-four'];
const spell = (n) => SPELL[n] || String(n);

async function start() {
  let list;
  try { list = await ask('/api/lineups'); } catch (e) { problem(e.message); return; }

  const host = $('chapters');
  let n = 0;
  for (const item of list) {
    if (item.slug === 'one-genre') continue;
    let data;
    try { data = await ask(`/api/lineups/${item.slug}`); } catch { continue; }
    n += 1;
    const sec = chapter(data, item.slug, n);
    host.appendChild(sec);
    if (item.slug === 'sundance2024') {
      const hook = el('section', 'panel reveal');
      hook.id = 'panel';
      host.appendChild(hook);
      panel(hook, { slug: item.slug }, data.films.map((f) => f.title));
    }
  }
  $('loading').hidden = true;
  if (!n) { problem('No programmes could be read.'); return; }

  viewTabs();
  tests();
  revealAll();
  stickyBar();
  backToTop();
}

function chapter(d, slug, index) {
  const sec = el('section', 'chapter reveal');
  sec.dataset.slug = slug;

  const title = el('p', 'chapter-title');
  if (index) title.appendChild(el('span', 'num', String(index)));
  title.appendChild(document.createTextNode(d.name));
  if (d.reading && d.reading !== 'films') {
    title.appendChild(el('span', 'reading', `read as ${d.reading}`));
  }
  sec.appendChild(title);
  sec.appendChild(verdict(d));

  const fig = el('div', 'figure');
  const cols = el('div', 'columns');
  const spend = el('div', 'spend');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'threads');
  svg.setAttribute('aria-hidden', 'true');
  const legend = el('p', 'legend');
  fig.append(cols, spend, svg, legend);
  sec.appendChild(fig);

  board(d, { cols, spend, svg, legend });
  return sec;
}

function verdict(d) {
  const h = d.headline;
  const wrap = document.createDocumentFragment();
  const line = el('h2', 'verdict-line');
  const put = (t) => line.appendChild(document.createTextNode(t));
  const num = (n) => line.appendChild(el('b', null, String(n)));

  num(h.films); put(` ${d.nouns || 'items'}`);
  if (h.origins > 1) { put(' from '); num(h.origins); put(' countries'); }
  put(' reach '); num(h.clusters);
  put(h.clusters === 1 ? ' audience.' : ' audiences.');
  wrap.appendChild(line);

  wrap.appendChild(el('p', 'verdict-sub', h.duplicate_slots > 0
    ? `${h.duplicate_slots} of the ${h.films} slots pay for an audience the `
      + `lineup already has. The largest group takes ${h.largest_cluster}.`
    : 'Every slot reaches a group no other slot reaches.'));
  return wrap;
}

function filmNode(f) {
  const n = el('span', 'film');
  n.dataset.title = f.title;
  n.appendChild(document.createTextNode(f.title));
  if (f.year) n.appendChild(el('span', 'year', String(f.year)));
  if (f.origin) n.appendChild(el('span', 'origin', f.origin));
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

function columnHead(count) {
  const h = el('div', 'column-head');
  h.appendChild(el('span', 'column-size', String(count)));
  h.appendChild(document.createTextNode(' '));
  h.appendChild(el('span', 'column-what',
    count === 1 ? 'film · its own audience group'
                : 'films · one audience group'));
  return h;
}

function board(d, ui) {
  const { cols, spend, svg, legend } = ui;
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
      'In each group, these two films reach the same people. Drop either one '
      + 'and you still cover that audience.'));
    spend.appendChild(head);

    const rows = el('div', 'spend-rows');
    d.clusters.forEach((c) => {
      const cell = el('div', 'spend-cell');
      cell.style.flex = weight(c.films.length);
      if (c.films.length >= 3) {
        const pairs = d.tightest.filter((t) => t.cluster === c.index).slice(0, 3);
        const ul = el('ul');
        pairs.forEach((t) => ul.appendChild(el('li', null, `${t.a} or ${t.b}`)));
        if (pairs.length) cell.appendChild(ul);
      }
      rows.appendChild(cell);
    });
    spend.appendChild(rows);
  };

  const settle = () => {
    cols.textContent = '';
    d.clusters.forEach((c, i) => {
      const col = el('div', 'column');
      col.style.flex = weight(c.films.length);
      col.appendChild(columnHead(c.films.length));
      c.films.slice()
        .sort((a, b) => byTitle[b].isolation - byTitle[a].isolation)
        .forEach((t) => col.appendChild(nodes.get(t) || filmNode(byTitle[t])));
      cols.appendChild(col);
    });
    spendBand();
    legendText(d, legend);
  };

  if (reduced) {
    settle();
    if (ui.onSettle) ui.onSettle();
    requestAnimationFrame(() => threads(d, ui));
    return;
  }

  const first = el('div', 'column');
  first.style.flex = weight(d.films.length);
  const head = el('div', 'column-head');
  head.appendChild(el('span', 'column-size', String(d.films.length)));
  head.appendChild(document.createTextNode(' '));
  head.appendChild(el('span', 'column-what', 'films · as the festival lists them'));
  first.appendChild(head);
  [...d.films].sort((a, b) => a.title.localeCompare(b.title)).forEach((f) => {
    const n = filmNode(f);
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
    const done = () => {
      if (ui.onSettle) ui.onSettle();
      requestAnimationFrame(() => threads(d, ui));
    };
    Promise.all(moving.map((a) => a.finished)).then(done).catch(done);
  }, 0.15);
}

function legendText(d, node) {
  node.textContent = '';
  const st = d.stability;
  if (st && st.ari != null) {
    const shaky = (st.clusters || []).filter(
      (c) => c.lift != null && c.lift < 0.25);
    node.appendChild(el('b', null, 'Drop any one film'));
    node.appendChild(document.createTextNode(
      `, re-rank the rest, re-choose the number of groups, and these come `
      + `back: ARI ${st.ari.toFixed(2)} over ${st.runs} runs, each group `
      + `measured against what a group its size scores on shuffled ranks. `));
    if (shaky.length) {
      node.appendChild(document.createTextNode(
        `${shaky.length === 1 ? 'One group of ' : 'Groups of '}`
        + `${shaky.map((c) => c.size).join(' and ')} `
        + `${shaky.length === 1 ? 'holds' : 'hold'} less firmly than the rest. `));
    }
  }
  const total = d.clusters.length;
  const say = (t) => node.appendChild(document.createTextNode(t));

  if (d.bridges.length) {
    const b = d.bridges[0];
    node.appendChild(el('b', null, b.film));
    say(b.connects.length >= total
      ? ` is the only route between the groups. Cut it and the programme becomes `
        + `${total} separate evenings. `
      : ` links ${b.connects.length} of the ${total} groups; the rest were never `
        + 'joined. ');
  } else {
    say(`Nothing joins the groups: ${total} separate evenings sharing a venue. `);
  }

  const lost = losses(d);
  if (lost) say(lost + ' ');
  if (d.films.some((f) => f.coverage < 0.5)) {
    say('Faded titles had less affinity data to place them.');
  }
}

function threads(d, { cols, svg }) {
  svg.innerHTML = '';
  if (!d.bridges || !d.bridges.length) return;
  if (window.matchMedia('(max-width: 760px)').matches) return;

  const box = svg.getBoundingClientRect();
  const find = (t) => cols.querySelector(`.film[data-title="${CSS.escape(t)}"]`);

  d.bridges.slice(0, 1).forEach((b) => {
    const src = find(b.film);
    if (!src) return;
    const s = src.getBoundingClientRect();
    const x1 = s.left - box.left + s.width;
    const y1 = s.top - box.top + s.height / 2;
    const done = new Set();

    (b.via || []).forEach((t) => {
      const node = find(t);
      if (!node) return;
      const cluster = d.clusters.find((c) => c.films.includes(t));
      if (!cluster || done.has(cluster.index)) return;
      done.add(cluster.index);

      const e = node.getBoundingClientRect();
      const x2 = e.left - box.left;
      const y2 = e.top - box.top + e.height / 2;
      const mx = (x1 + x2) / 2;
      const shape = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
      const under = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      under.setAttribute('class', 'under');
      under.setAttribute('d', shape);
      svg.appendChild(under);
      const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', shape);
      svg.appendChild(p);
      const len = p.getTotalLength();
      p.style.setProperty('--len', len);
      under.style.setProperty('--len', len);
    });
  });
}

function controlFigure(d, host) {
  host.textContent = '';
  const cols = el('div', 'columns tight');
  d.clusters.slice().sort((a, b) => b.films.length - a.films.length)
    .forEach((c) => {
      const col = el('div', 'column');
      col.appendChild(columnHead(c.films.length));
      c.films.slice().sort().forEach((t) => {
        const row = el('span', 'film');
        row.appendChild(document.createTextNode(t));
        col.appendChild(row);
      });
      cols.appendChild(col);
    });
  host.appendChild(cols);
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
  const head = (label) => {
    const tr = el('tr', 'head');
    const td = el('td', null, label);
    td.colSpan = 4;
    tr.appendChild(td);
    t.appendChild(tr);
  };
  const row = (p) => {
    const tr = el('tr');
    tr.appendChild(el('td', 'd', p.distance.toFixed(2)));
    tr.appendChild(el('td', null, `${p.a} / ${p.b}`));
    tr.appendChild(el('td', 'r', p.r.toFixed(2)));
    tr.appendChild(el('td', 'n', `${p.n.toLocaleString()} rated both`));
    t.appendChild(tr);
  };
  head('Slate distance \u2502 agreement \u2502 rated both');
  ml.closest.forEach(row);
  ml.furthest.forEach(row);
  return t;
}

function stabilityTable(st) {
  const t = el('table', 'bars-table');
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

  const test = (n, question) => {
    const art = el('article', 'test');
    const h = el('h3');
    h.appendChild(el('span', 'num', String(n)));
    h.appendChild(document.createTextNode(question));
    art.appendChild(h);
    host.appendChild(art);
    return art;
  };
  const say = (art, text, cls) => art.appendChild(el('p', cls || null, text));

  if (control) {
    const art = test(1, 'Does Slate just group by genre?');
    say(art, `${Caps(spell(control.films.length))} science fiction films were `
      + 'given to Slate as one lineup. Every one of them carries the same '
      + 'genre tag. If Slate were grouping by genre, they would all come back '
      + 'as one audience.');
    const fig = el('div');
    controlFigure(control, fig);
    art.appendChild(fig);
    say(art, `They come back as ${spell(control.clusters.length)}. So Slate is `
      + 'not grouping by genre: it is reading something the genre tag does not '
      + 'contain.', 'closing-line');
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
    art.appendChild(mlTables(ml, 'pairs'));
    say(art, 'The further apart Slate places two films, the less the people '
      + `who saw both agreed about them. Across all ${ml.pairs} pairs, that `
      + `relationship measures ${ml.rho.toFixed(3)} (Spearman). This is shown `
      + 'in a dataset Qloo never touched.');
    say(art, 'Hence the groups Slate makes match how people actually behave.',
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
    art2.appendChild(ul);
    say(art2, 'Genre and release year come from MovieLens itself. Popularity '
      + 'comes from Qloo.');
    say(art2, 'For each measure, Slate correlated it against the agreement '
      + `numbers across all ${ml.pairs} pairs. A number near zero means that `
      + 'measure tells you nothing about whether two films\u2019 viewers '
      + 'agreed. The further from zero, the more it tells you.');
    art2.appendChild(mlTables(ml, 'baselines'));
    say(art2, `Next to Slate\u2019s ${ml.rho.toFixed(3)}, the other three sit `
      + 'near zero. Slate\u2019s distance tells you far more about whether two '
      + 'films\u2019 viewers agreed than any of them.');
    say(art2, 'Hence metadata cannot make these groups. Slate is reading '
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
    if (v && v.lineup_ari) art.appendChild(ariTable(v.lineup_ari));
    say(art, 'Each group is also checked on its own with Jaccard: of the '
      + 'films that were in that group, how many are still together '
      + 'afterwards.');
    say(art, 'Slate shuffles every film\u2019s ranking so the order carries no '
      + 'information, then runs the same test again. Each run removes one '
      + 'film and re-clusters, and for each group counts how many of its '
      + 'films are still together: two of two is 1.00, three of four is 0.75. '
      + 'The scores are averaged over all the runs.');
    art.appendChild(stabilityTable(st));
    say(art, 'The effect is most visible on small groups. If a group has only '
      + 'two films and you remove one, the pair is gone, so Jaccard always '
      + 'scores it badly however real it was. On shuffled rankings a pair '
      + 'gets about 0.44. A real pair scoring 0.69 is above that, and the gap '
      + 'is what counts.');
    say(art, 'Hence, based on the results shown, the groups do not depend on '
      + 'any one film being in the lineup.', 'closing-line');
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
    art.appendChild(ul);
    say(art, 'If betweenness is really popularity in disguise, the two should '
      + 'rise and fall together in every lineup. Each number below is the '
      + 'correlation between them across all the films in that lineup '
      + '(Spearman):');
    art.appendChild(bridgeTable(b));
    say(art, 'They do not. Two lineups go one way, two the other, and across '
      + `all ${b.films} films the relationship is nothing. In the science `
      + 'fiction lineup it runs strongly negative, which means the least '
      + 'popular films carry the most routes.');
    say(art, 'High betweenness alone is not enough to be called a bridge. '
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
      art.appendChild(p);
    }
    say(art, 'Hence a bridge is not the most popular film wearing a label.',
      'closing-line');
  }

  const sec = $('checked');
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

  const say = el('p', 'panel-diff');
  const fig = el('div', 'panel-figure');
  const foot = el('p', 'panel-foot');
  host.append(say, fig, foot);

  const fewer = el('div', 'panel-fewer');
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

  const drawChips = () => {
    chips.textContent = '';
    state.films.forEach((t) => {
      const out = state.drop.includes(t);
      const chip = el('button', out ? 'chip gone' : 'chip');
      chip.type = 'button';
      chip.appendChild(document.createTextNode(t));
      if (!out) chip.appendChild(el('span', 'chip-x', '\u00d7'));
      chip.onclick = () => {
        state.drop = out ? state.drop.filter((x) => x !== t)
                         : state.drop.concat(t);
        state.keep = null;
        run();
      };
      chips.appendChild(chip);
    });
  };

  const drawSizes = (n) => {
    pick.textContent = '';
    for (let k = n - 1; k >= 4; k -= 1) {
      pick.appendChild(el('option', null, String(k)));
    }
    count.textContent = `of the ${n}`;
    findBtn.disabled = n <= 4;
  };

  const run = async () => {
    say.textContent = 'Working it out';
    fig.textContent = '';
    try {
      const body = { drop: state.drop, add: state.add };
      if (source.slug) body.slug = source.slug;
      else body.films = source.films;
      if (state.keep) body.keep = state.keep;

      const d = await ask('/api/panel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      say.textContent = (d.diff && d.diff.line) || '';
      fig.textContent = '';
      const sec = chapter(d, null);
      sec.classList.add('shown');
      const head = sec.querySelector('.chapter-title');
      if (head) head.remove();
      fig.appendChild(sec);

      foot.textContent = '';
      const bits = [];
      if (d.dropped && d.dropped.length) bits.push(`Removed: ${d.dropped.join(', ')}.`);
      if (d.added && d.added.length) bits.push(`Added: ${d.added.join(', ')}.`);
      if (bits.length) {
        foot.appendChild(document.createTextNode(`${bits.join(' ')} `));
        const reset = el('button', 'linky', 'Reset to the real lineup');
        reset.type = 'button';
        reset.onclick = () => {
          state.drop = []; state.add = []; state.keep = null;
          state.films = baseFilms.slice();
          drawChips(); run();
        };
        foot.appendChild(reset);
      }
      drawSizes(d.films.length);
    } catch (e) {
      say.textContent = '';
      fig.textContent = '';
      failure(e, fig, run);
    }
  };

  addBtn.onclick = () => {
    const t = field.value.trim();
    if (!t) return;
    state.add = state.add.concat(t);
    state.films = state.films.concat(t);
    state.keep = null;
    field.value = '';
    drawChips();
    run();
  };
  field.onkeydown = (ev) => { if (ev.key === 'Enter') addBtn.onclick(); };
  findBtn.onclick = () => { state.keep = Number(pick.value); run(); };

  drawChips();
  drawSizes(baseFilms.length);
  run();
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
  const box = el('div', 'coverage');
  box.appendChild(el('h4', null,
    `Analysis based on ${used} of the ${used + gone} films you gave.`));
  if (d.unresolved && d.unresolved.length) {
    const p = el('p');
    p.appendChild(el('b', null, 'Could not match: '));
    p.appendChild(document.createTextNode(d.unresolved.join(', ')
      + '. Qloo did not recognise these titles. A year in brackets often fixes it.'));
    box.appendChild(p);
  }
  if (d.excluded && d.excluded.length) {
    const p = el('p');
    p.appendChild(el('b', null, 'No affinity data: '));
    p.appendChild(document.createTextNode(d.excluded.join(', ')
      + '. These matched, but no other film returned them, so there is nothing '
      + 'to place them with. Including them would be a guess.'));
    box.appendChild(p);
  }
  box.appendChild(el('p', 'limit',
    'The groups below describe the films that were analysed, not the full '
    + 'list you submitted.'));
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

async function runOwn() {
  const raw = $('own-input').value.split('\n').map((s) => s.trim()).filter(Boolean);
  const out = $('own-result');
  const btn = $('own-run');
  out.textContent = '';

  if (raw.length < 4) {
    out.appendChild(status('thin', 'Not enough films to read a shape.',
      `Slate needs at least four. You have ${raw.length}. A shape needs `
      + 'something to be the shape of.', []));
    return;
  }
  const films = raw.slice(0, 24);

  btn.disabled = true;
  btn.textContent = 'Reading';
  const waiting = el('div', 'waiting');
  waiting.appendChild(el('span', 'pulse'));
  waiting.appendChild(el('p', null,
    `Asking Qloo about ${films.length} titles. That is one live call for `
    + 'each, so it takes a moment \u2014 the four lineups above are cached, '
    + 'this one is not.'));
  out.appendChild(waiting);

  try {
    const d = await ask('/api/analyse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ films, name: 'Your slate' }),
    });
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
    out.textContent = '';
    failure(e, out, runOwn);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Find the shape';
  }
}

$('own-run').onclick = runOwn;

start();
