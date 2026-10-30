const fs = require('fs');
const raw = fs.readFileSync('static/app.js', 'utf8');
const src = raw
  .replace(/`(?:\\.|[^`\\])*`/g, '``')
  .replace(/'(?:\\.|[^'\\\n])*'/g, "''")
  .replace(/"(?:\\.|[^"\\\n])*"/g, '""');

const defined = new Set();
for (const m of src.matchAll(/function\s+([A-Za-z_$][\w$]*)/g)) defined.add(m[1]);
for (const m of src.matchAll(/(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/g)) defined.add(m[1]);
for (const m of src.matchAll(/(?:const|let|var)\s*\{([^}]+)\}/g))
  m[1].split(',').forEach(x => defined.add(x.split(':').pop().trim()));
                                            
for (const m of src.matchAll(/(?:const|let|var)\s*\[([^\]]+)\]/g))
  m[1].split(',').forEach(x => { const n = x.trim(); if (n) defined.add(n); });
for (const m of src.matchAll(/function[^(]*\(([^)]*)\)/g))
  m[1].split(',').forEach(x => { const n = x.trim().split(/[=\s]/)[0]; if (n) defined.add(n); });
for (const m of src.matchAll(/\(([^)]*)\)\s*=>/g))
  m[1].split(',').forEach(x => { const n = x.trim().split(/[=\s]/)[0]; if (n) defined.add(n); });
for (const m of src.matchAll(/([A-Za-z_$][\w$]*)\s*=>/g)) defined.add(m[1]);
for (const m of src.matchAll(/\.forEach\(\(([^)]*)\)/g))
  m[1].split(',').forEach(x => defined.add(x.trim()));
for (const m of src.matchAll(/for\s*\(\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g)) defined.add(m[1]);
for (const m of src.matchAll(/catch\s*\(\s*([A-Za-z_$][\w$]*)/g)) defined.add(m[1]);

const globals = new Set(['window','document','console','fetch','Math','JSON','Object',
  'Array','Number','String','Boolean','Set','Map','Promise','Date','CSS','Error',
  'requestAnimationFrame','setTimeout','clearTimeout','setInterval','IntersectionObserver',
  'parseInt','parseFloat','isNaN','location','navigator','encodeURIComponent','$','el']);

const missing = new Set();
for (const m of src.matchAll(/(^|[^.\w$'"`])([a-z_$][\w$]*)\s*\(/gm)) {
  const name = m[2];
  if (['if','for','while','switch','catch','return','typeof','function','new',
       'await','of','in','do','else','try','async'].includes(name)) continue;
  if (defined.has(name) || globals.has(name)) continue;
  missing.add(name);
}
if (missing.size) { console.log('UNDEFINED:', [...missing].join(', ')); process.exit(1); }
console.log('every function called is defined');
