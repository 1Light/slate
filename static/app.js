const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const letterFor = (i) => LETTERS[i] || String(i + 1);
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
    .map((tab) => {
      const href = tab.getAttribute('href') || '';
      if (!href.startsWith('#') || href.length < 2) return null;
      return { tab, at: document.getElementById(href.slice(1)) };
    })
    .filter((s) => s && s.at);
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
    const lanes = groups.length + (extra === 'span' ? 1 : 0);
    const gap = card.w * 0.55;
    const wide = lanes * card.w + (lanes - 1) * gap;
    const lean = extra === 'apart' ? card.w * 0.8 : 0;
    const left = Math.max(card.w * 0.3, (room - wide - lean) / 2);
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
      if (plan.notes) tag.appendChild(el('em', null, `${count} titles`));
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
      const last = groups.length - 1;
      const deep = (groups[last] - 1) * step;
      spots.push({
        x: laneAt(last) + card.w * 0.62,
        y: top + deep + card.h * 0.56,
        z: 40, turn: -20, role: 'apart',
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
  }
  if (!n) { problem('No programmes could be read.'); return; }

  const steps = [
    ['the agent examples', agentSection],
    ['the media tabs', viewTabs],
    ['the evidence', tests],
    ['reveal on scroll', revealAll],
    ['the sticky header', stickyBar],
    ['back to top', backToTop],
    ['the scroll spy', markWhere],
    ['the hero animation', heroStage],
    ['the bridge animation', () => markStage('stage-bridge', 'bridge')],
    ['the outlier animation', () => markStage('stage-outlier', 'outlier')],
  ];
  for (const [what, run] of steps) {
    try {
      run();
    } catch (e) {
      console.error(`Slate could not set up ${what}:`, e);
    }
  }
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
  const links = el('div', 'links');
  const spend = el('div', 'spend');
  const legend = el('div', 'legend');
  taken.hidden = true;
  fig.append(sizes, cols, taken, links, spend, legend);
  sec.appendChild(fig);

  board(d, { cols, spend, legend, sizes, taken, links });
  return sec;
}

function verdict(d) {
  const h = d.headline;
  const line = el('h2', 'verdict-line');
  const put = (t) => line.appendChild(document.createTextNode(t));
  const num = (n) => line.appendChild(el('b', null, String(n)));

  num(h.films); put(` ${d.nouns || 'items'}`);
  if (h.origins > 1) { put(' from '); num(h.origins); put(' countries'); }
  if (d.weak) {
    put(' do not separate.');
    return line;
  }
  put(' separate into '); num(h.clusters);
  put(h.clusters === 1 ? ' group.' : ' groups.');
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
    n.appendChild(el('span', 'tag', 'new'));
  }
  if (f.role === 'bridge') n.classList.add('bridge');
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

function columnHead(count, index, noun, nouns) {
  const h = el('div', 'column-head');
  if (index != null) h.appendChild(el('span', 'column-letter', letterFor(index)));
  h.appendChild(el('span', 'column-size', String(count)));
  h.appendChild(document.createTextNode(' '));
  h.appendChild(el('span', 'column-what',
    count === 1 ? `${noun || 'film'} · its own group`
                : `${nouns || 'films'} · one group`));
  return h;
}

function board(d, ui) {
  const { cols, spend, legend } = ui;

  const bridged = new Set((d.bridges || []).map((b) => b.film));
  const keep = (c) => c.films.filter((t) => !bridged.has(t));
  const byTitle = Object.fromEntries(d.films.map((f) => [f.title, f]));
  const nodes = new Map();

  const weight = (n) => `${n} 1 0`;

  const spendBand = () => {
    spend.textContent = '';
    const held = new Set(d.locked || []);
    const usable = d.clusters.filter((c) => c.films.length >= 3
      && d.tightest.some((t) => t.cluster === c.index
        && !held.has(t.a) && !held.has(t.b)));
    if (!usable.length) return;

    if (d.weak) { spend.textContent = ''; return; }
    const head = el('div', 'spend-head');
    head.appendChild(el('h4', null, 'If you need to free a slot'));
    head.appendChild(el('p', null,
      'These pairs overlap more than any others in their group. Drop either '
      + 'one and the group still covers its audience.'));
    spend.appendChild(head);

    const rows = el('ul', 'spend-rows');
    let found = 0;
    d.clusters.forEach((c, i) => {
      if (c.films.length < 3) return;
      const pairs = d.tightest
        .filter((t) => t.cluster === c.index
          && !bridged.has(t.a) && !bridged.has(t.b)
          && !held.has(t.a) && !held.has(t.b))
        .slice(0, 1);
      pairs.forEach((t) => {
        const li = el('li');
        li.appendChild(el('span', 'spend-letter', letterFor(i)));
        li.appendChild(document.createTextNode(`${t.a} or ${t.b}`));
        rows.appendChild(li);
        found += 1;
      });
    });
    if (!found) { spend.textContent = ''; return; }
    spend.appendChild(rows);
  };

  const linkBand = () => {
    if (!ui.links) return;
    ui.links.textContent = '';
    const list = (d.bridges || []);
    if (!list.length || d.weak) return;

    const head = el('div', 'links-head');
    head.appendChild(el('h4', null, 'Bridges'));
    head.appendChild(el('p', null,
      'Each bridge is close to titles in more than one group, so it '
      + 'connects them instead of fitting into just one.'));
    ui.links.appendChild(head);

    const rows = el('div', 'links-rows');
    list.forEach((b) => {
      const one = el('div', 'link');
      const f = byTitle[b.film];
      const name = el('p', 'link-name');
      name.dataset.title = b.film;
      name.appendChild(document.createTextNode(b.film));
      if (f && f.year) name.appendChild(el('span', 'year', String(f.year)));
      one.appendChild(name);
      if (f && f.origin) one.appendChild(el('p', 'link-where', f.origin));
      one.appendChild(el('span', 'link-spans',
        (b.connects || []).map(letterFor).join('\u00b7')));
      rows.appendChild(one);
    });
    ui.links.appendChild(rows);
    if (window.afterLinks) window.afterLinks(ui.links);
  };

  const settle = () => {
    cols.textContent = '';
    d.clusters.forEach((c, i) => {
      const mine = keep(c);
      const col = el('div', 'column');
      col.appendChild(columnHead(mine.length, i, d.noun, d.nouns));
      mine.slice()
        .sort((a, b) => byTitle[b].isolation - byTitle[a].isolation)
        .forEach((t) => col.appendChild(nodes.get(t) || filmNode(byTitle[t], fresh)));
      cols.appendChild(col);
    });
    linkBand();
    spendBand();
    if (ui.sizes) {
      ui.sizes.textContent = '';
      const counts = d.clusters.map((c) => keep(c).length).filter(Boolean);
      const most = Math.max(1, ...counts);
      counts.forEach((n) => {
        const bar = el('span');
        bar.style.flex = String(n);
        bar.style.opacity = String(0.4 + 0.6 * (n / most));
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
  head.appendChild(el('span', 'column-what',
    `${d.nouns || 'titles'} \u00b7 as you gave them`));
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

function withTitles(node, text, names) {
  const marks = (names || []).filter(Boolean)
    .sort((a, b) => b.length - a.length);
  if (!marks.length) { node.appendChild(document.createTextNode(text)); return; }
  let rest = text;
  while (rest) {
    let at = -1;
    let hit = null;
    marks.forEach((m) => {
      const i = rest.indexOf(m);
      if (i !== -1 && (at === -1 || i < at)) { at = i; hit = m; }
    });
    if (at === -1) { node.appendChild(document.createTextNode(rest)); return; }
    if (at) node.appendChild(document.createTextNode(rest.slice(0, at)));
    node.appendChild(el('i', 'tname', hit));
    rest = rest.slice(at + hit.length);
  }
}

function legendText(d, node) {
  node.textContent = '';
  const works = d.films.map((f) => f.title)
    .concat(d.excluded || [], d.unresolved || []);
  const line = (text) => {
    const p = el('p');
    withTitles(p, text, works);
    node.appendChild(p);
  };

  if (d.weak) {
    line('No clear separation under this analysis. Slate found no grouping '
      + `of these ${d.films.length} ${d.nouns || 'items'} where the lines `
      + 'between groups scored well enough to show.');
    return;
  }

  const alone = d.films.filter((f) => f.role === 'alone').map((f) => f.title);
  if (alone.length === 1) {
    line(`${alone[0]} is an outlier. It covers taste nothing else here `
      + 'covers.');
  } else if (alone.length > 1) {
    line(`${nameList(alone)} are outliers. Each covers taste nothing else `
      + 'here covers.');
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
        row.dataset.title = t;
        row.appendChild(document.createTextNode(t));
        col.appendChild(row);
      });
      cols.appendChild(col);
    });
  host.appendChild(cols);
}

function groupTable(g) {
  const t = el('table', 'pairs');
  const head = el('tr', 'head');
  [['', ''], ['Audience overlap', 'r']].forEach(([label, cls]) => {
    head.appendChild(el('td', cls, label));
  });
  t.appendChild(head);
  const row = (what, value) => {
    const tr = el('tr');
    tr.appendChild(el('td', 'pair', what));
    tr.appendChild(el('td', 'r strong', value.toFixed(2)));
    t.appendChild(tr);
  };
  row(`Same group, ${g.inside_pairs} pairs`, g.inside_mean);
  row(`Different groups, ${g.between_pairs} pairs`, g.between_mean);
  return t;
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
    ml.baselines.forEach((x, i) => {
      const tr = el('tr', i === 0 ? 'win' : null);
      tr.appendChild(el('td', 'who', x.name));
      tr.appendChild(el('td', 'd',
        `${x.rho >= 0 ? '+' : ''}${x.rho.toFixed(3)}`));
      bt.appendChild(tr);
    });
    return bt;
  }
  const t = el('table', 'pairs');
  const headRow = () => {
    const tr = el('tr', 'head');
    ['Distance', 'Pair', 'Audience overlap', 'Rated both'].forEach((label, i) => {
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
    const share = p.phi != null ? p.phi.toFixed(2)
      : p.overlap != null ? `${(p.overlap * 100).toFixed(0)}%`
        : p.r.toFixed(2);
    tr.appendChild(el('td', 'r strong', share));
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
  ['Group', 'Stayed together', 'On shuffled rankings', 'The gap']
    .forEach((label, i) => {
      head.appendChild(el('td', i === 0 ? 'who' : 'd', label));
    });
  t.appendChild(head);
  const pc = (x) => `${Math.round(x * 100)}%`;
  st.clusters.filter((c) => c.lift != null).forEach((c) => {
    const tr = el('tr', 'win');
    tr.appendChild(el('td', 'who', `${c.size} films`));
    tr.appendChild(el('td', 'd', pc(c.jaccard)));
    tr.appendChild(el('td', 'd', pc(c.chance)));
    tr.appendChild(el('td', 'd',
      `+${Math.round((c.jaccard - c.chance) * 100)}`));
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
      + 'science-fiction tag.');
    const fig = el('div', 'control-figure');
    controlFigure(control, fig);
    art.appendChild(fig);
    below(art, `Slate separates them into ${spell(control.clusters.length)} `
      + 'groups using Qloo’s affinity rankings. The shared tag alone does '
      + 'not describe those differences.', 'closing-line');
  }

  if (v && v.movielens) {
    const ml = v.movielens;
    const art = test(2, 'Do the groups match how people actually behave?');
    say(art, 'Everything above comes from Qloo. To check whether its results '
      + 'reflect how people actually behave, Slate used an independent '
      + 'dataset: MovieLens, 32 million film ratings published by a research '
      + 'group at the University of Minnesota.');

    const g = v && v.groups;
    if (g) {
      const measured = g.lineups || [];
      const sizes = measured.map((row) => row.titles);
      say(art, sizes.length === 2
        ? `Slate tested two lineups with sufficient MovieLens coverage, evaluating ${sizes[0]} films in one and ${sizes[1]} in the other. Each lineup was clustered separately, using Qloo alone.`
        : 'Slate tested lineups with sufficient MovieLens coverage. Each lineup was clustered separately, using Qloo alone.', 'sub-head');
      say(art, 'Every possible pair within a lineup was then constructed, '
        + 'and Slate used MovieLens ratings to determine each pair\u2019s '
        + 'audience overlap. This is based on which users rated both films, '
        + 'rather than whether they liked them.');
      say(art, 'All the pairs Slate had placed in the same group, across '
        + 'both lineups, were pooled into one pile; those it had split apart '
        + 'went into another. Audience overlap was averaged for each '
        + `pile. For pairs in the same group it came to ${g.inside_mean.toFixed(2)}, `
        + `and for pairs in different groups ${g.between_mean.toFixed(2)}. `
        + `The gap is ${g.gap.toFixed(2)}.`);
      art.appendChild(titled(null, groupTable(g)));
      below(art, 'Slate randomly moved films between groups, keeping the '
        + 'same number of films in each group, and measured again '
        + `${Number(g.shuffles).toLocaleString('en-GB')} times. `
        + (g.reached === 0
          ? 'None produced a gap as large as Slate’s.'
          : `${g.reached} produced a gap as large as Slate’s.`));
    }

    say(art, 'Does the distance behind the groups hold up?', 'sub-head');
    say(art, 'The groups are built from one number: how far apart Slate '
      + 'places two films. That number comes from Qloo\u2019s rankings. Slate '
      + 'asks Qloo about each film, sees where it places the others, and '
      + 'averages the two directions.');
    say(art, `For the ${ml.overlap_pairs} pairs in the science fiction season, here `
      + 'are the four Slate places closest and the four it places furthest. '
      + 'Audience overlap is measured from MovieLens.');
    art.appendChild(titled(null, mlTables(ml, 'pairs')));
    if (ml.overlap_rho != null) {
      below(art, `Across all ${ml.overlap_pairs} pairs, Slate measured the `
        + 'relationship between two things: how far apart it places a pair, '
        + 'and how much their audiences overlap. The measure runs from '
        + '\u22121 to +1. Zero means no consistent tendency for one measure '
        + 'to rise or fall with the other; \u22121 means a perfect ranking in '
        + 'the opposite direction, where more distance always means less '
        + 'overlap.');
      below(art, `That relationship scored ${ml.overlap_rho.toFixed(3)}. The `
        + 'further apart Slate places two films, the less their audiences '
        + 'tend to overlap.');
      below(art, 'Could the result simply reflect how widely rated the '
        + 'films are? Slate checked this using the number of MovieLens '
        + 'ratings for the less-rated film in each pair. Its relationship '
        + 'with audience overlap scored '
        + `${ml.overlap_popularity_rho > 0 ? '+' : ''}${ml.overlap_popularity_rho.toFixed(3)}.`);
      below(art, 'Slate also checked whether films released closer together '
        + 'tend to share an audience. That relationship scored −0.596. '
        + 'Slate’s distance showed the strongest relationship with audience '
        + `overlap, at ${ml.overlap_rho.toFixed(3)}.`);
    }
    below(art, 'Finally the same measure was run on distance against how '
      + 'closely the people who saw both films agreed about them. It scored '
      + `${ml.rho.toFixed(3)}. The further apart Slate places two films, the `
      + 'less closely their viewers’ ratings tended to agree.');
    below(art, 'These checks support a relationship between Slate’s '
      + 'grouping, its distances and MovieLens rating behaviour on the '
      + 'films tested.',
      'closing-line');

    const art2 = test('2b', 'Could metadata explain rating agreement as well?');
    art2.classList.add('sub');
    say(art2, 'Could genre, release year or popularity explain the same '
      + 'pattern? Slate compared each with the rating agreement between '
      + 'films in MovieLens.');
    say(art2, `Every pair of films in the lineup, ${ml.pairs} of them, was `
      + 'tested again against the same MovieLens agreement numbers, using a '
      + 'different measure of closeness each time:');
    const ul = el('ul', 'defs');
    [['Slate distance', 'how far apart Slate places the two films'],
     ['Shared genres', 'the proportion of their combined genre tags that both films share'],
     ['Years apart', 'the gap between their release years'],
     ['Popularity gap', 'the difference between their Qloo popularity scores']]
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
      + 'measure has little consistent relationship with how closely the '
      + 'viewers’ ratings agreed. A larger absolute number means a stronger '
      + 'relationship in this sample.');
    art2.appendChild(titled('Correlated against the same agreement numbers',
      mlTables(ml, 'baselines')));
    below(art2, `On these ${ml.pairs} pairs, Slate’s distance had a stronger `
      + 'relationship with rating agreement than shared genres, '
      + 'release-year difference or popularity difference.', 'closing-line');
  }

  if (control && control.stability) {
    const st = control.stability;
    const art = test(3, 'How sensitive are the groups to the lineup itself?');
    say(art, 'A useful grouping should remain reasonably stable when an '
      + 'individual film leaves. Slate checks this by removing each film in '
      + 'turn and analysing the remaining lineup. It re-ranks the remaining '
      + 'films using the stored Qloo rankings, rebuilds the distances and '
      + 'lets the engine choose the groups again. Then it compares the result '
      + 'against the original.');
    say(art, 'The more the same films stay together after one is removed, '
      + 'the less the grouping depends on that film being present.');
    say(art, 'The comparison is scored with the adjusted Rand index, a '
      + 'standard measure of how closely two groupings agree. A score of 1 '
      + 'means identical groupings, while a score around 0 means agreement '
      + 'no better than chance. Negative scores are also possible.');
    if (v && v.lineup_ari) {
      art.appendChild(titled(null, ariTable(v.lineup_ari)));
    }
    say(art, 'Each group is then checked on its own, using Jaccard: of the '
      + 'films that were in a group, how many are still together after a '
      + 'film is removed and the lineup re-clustered. The scores are '
      + 'averaged over every run.');
    say(art, 'The shuffled column shows what a group of that size scores '
      + 'when every film\u2019s ranking is randomised and the test is run '
      + 'again. This provides a comparison under random rankings. The gap '
      + 'shows how much more stable Slate’s groups were in this test.');
    art.appendChild(titled('Each group on its own, science fiction lineup',
      stabilityTable(st)));
    below(art, 'Across these four lineups, the groups remained largely '
      + 'stable when individual films were removed.', 'closing-line');
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
    below(art, 'The relationship varies by lineup: two correlations are '
      + `positive and two negative. Across all ${b.films} films, the pooled `
      + `correlation is weak at ${b.pooled_rho > 0 ? '+' : ''}${b.pooled_rho.toFixed(2)}.`);
    below(art, 'High betweenness alone is not enough to be called a bridge. '
      + 'Slate builds the graph three times, connecting each film to its 2, 3 '
      + 'and 4 nearest, and a film only qualifies if it stays in the top '
      + 'three every time. A film that ranks highly under one setting but '
      + 'falls away under another does not pass Slate’s bridge filter.');
    if (b.caught) {
      const p = el('p');
      p.appendChild(document.createTextNode(
        'Sundance shows that filter working. The film with the most routes '
        + 'through it is '));
      p.appendChild(el('i', null, b.caught.top_by_betweenness));
      p.appendChild(document.createTextNode(
        ', the most popular film in that lineup. Slate did not call it a '
        + 'bridge: it did not rank in the top three for betweenness across '
        + 'all of the 2, 3 and 4 nearest settings. '));
      p.appendChild(el('i', null, b.caught.bridges[0]));
      p.appendChild(document.createTextNode(' did, and was named instead.'));
      art.after.appendChild(p);

      const other = b.rows.find((r) => r.top_was_reported);
      if (other) {
        const q = el('p');
        q.appendChild(document.createTextNode(`${other.lineup} went the `
          + 'other way. '));
        q.appendChild(el('i', null, other.top_by_betweenness));
        q.appendChild(document.createTextNode(' tops betweenness there and '
          + 'is also the most popular film in the lineup, and it held '
          + 'across all three settings. Being popular does not disqualify a '
          + 'film from being a connector. It simply does not earn the label '
          + 'on its own.'));
        art.after.appendChild(q);
      }
    }
    below(art, 'Hence a bridge is not the most popular film wearing a label.',
      'closing-line');
  }

    const five = test(5, 'Does a group mean a fixed audience?');
    say(five, 'No. Slate measures how far apart items sit within the lineup '
      + 'you gave it, so a group is a statement about that lineup and '
      + 'nothing more.');
    say(five, 'Take four films that Slate put together and run them on their '
      + 'own. They separate again. Nothing changed about the films. The '
      + 'sixteen they were being compared against are gone, so the only '
      + 'differences left are the ones between those four.');
    say(five, 'This is true of how people compare films too. Give a person '
      + 'twenty films and they may group them one way. Give them four and '
      + 'they may group them another, because different similarities and '
      + 'differences stand out.');
    say(five, 'Slate compares possible divisions using silhouette scores: '
      + 'how closely an item sits within its own group compared with the '
      + 'nearest other group.');
    const found = el('p');
    found.appendChild(el('b', null, 'Slate chooses the minimum number of '
      + 'groups that achieves a near-optimal division.'));
    (five.after || five).appendChild(found);
    say(five, 'So the question Slate answers is this: given a lineup, which '
      + 'items overlap more in taste compared to all the others in it. It is '
      + 'not answering which items belong to a fixed audience group, because '
      + 'there is no universal grouping to belong to.');
    say(five, 'Hence a group describes the lineup, not a universally fixed '
      + 'set.', 'closing-line');
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
  const head = el('tr', 'head');
  ['Lineup', 'Adjusted Rand index'].forEach((label, i) => {
    head.appendChild(el('td', i === 0 ? 'who' : 'd', label));
  });
  t.appendChild(head);
  rows.forEach((r) => {
    const tr = el('tr', 'win');
    tr.appendChild(el('td', 'who', r.name));
    tr.appendChild(el('td', 'd', `+${r.ari.toFixed(2)}`));
    t.appendChild(tr);
  });
  return t;
}

function settleInto(fig, before, moved) {
  if (!before.size || reduced) return 0;
  let shifted = 0;
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
    shifted += 1;
    row.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` },
       { transform: 'none' }],
      { duration: mark.has(row.dataset.title) ? 640 : 460,
        easing: 'cubic-bezier(.3,.9,.3,1)', fill: 'both' });
  });
  return shifted;
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
    shape.appendChild(document.createTextNode(' groups becomes '));
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
      'Each candidate was added, the whole lineup re-clustered, and the '
      + 'result measured. None of them improved it.'));
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
      document.getElementById('festivals')
        ? [['Try again', retry, true],
           ['See a measured lineup', () => { location.hash = '#cannes'; }]]
        : [['Try again', retry, true]]));
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

if (document.getElementById('festivals')) start();