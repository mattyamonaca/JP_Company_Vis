// 絞り込みエクスプローラ: cube.json (属性の組み合わせ × 社数) をブラウザ側で集計する
import { stackedColumns, hBars, fmt, pct } from './charts.js';
const $ = id => document.getElementById(id);
const C = { s1: 'var(--s1)', s2: 'var(--s2)', s3: 'var(--s3)', s4: 'var(--s4)', s8: 'var(--s8)', muted: 'var(--deemph)' };
const cube = await (await fetch('data/cube.json')).json();
const D = cube.dims, R = cube.rows;
// 行の列: 0 year,1 pref,2 kind,3 status,4 closed_year,5 flags,6 kw(mask),7 jpx,8 field,9 count
const DIMS = [
  { key: 'year', col: 0, label: '設立年', help: '法人番号の指定年。2026年は8月末まで' },
  { key: 'kind', col: 2, label: '法人種別' },
  { key: 'status', col: 3, label: '出口・現在の状態', help: '上場＝EDINETコードリストで現在上場。閉鎖は登記記録の閉鎖事由（2026年8月末時点）' },
  { key: 'flags', col: 5, label: '属性', help: '大学発＝経産省データベース掲載。吸収した側＝他社を合併で承継した会社', bits: true },
  { key: 'pref', col: 1, label: '都道府県', collapsible: true },
  { key: 'closed_year', col: 4, label: '閉鎖した年', help: '登記記録が閉鎖された年', collapsible: true },
  { key: 'kw', col: 6, label: '商号キーワード（推定）', help: '商号に含まれる語からの推定。複数選択は「いずれかを含む」。精度は低い', bits: true },
  { key: 'jpx', col: 7, label: '上場企業の業種（EDINET 33業種）', help: '上場している会社にだけ付く', collapsible: true, skipZero: true },
  { key: 'field', col: 8, label: '大学発ベンチャーの技術分野', help: '大学発ベンチャーにだけ付く', collapsible: true, skipZero: true },
];
const sel = {}; for (const d of DIMS) sel[d.key] = new Set();
const passes = (r, d) => { const s = sel[d.key]; if (!s.size) return true; const v = r[d.col];
  if (d.bits) { let m = 0; for (const i of s) m |= 1 << i; return d.key === 'flags' ? (v & m) === m : (v & m) !== 0; }
  return s.has(v); };
const passesAll = (r, except) => DIMS.every(d => d === except || passes(r, d));

// ---- URL 同期 ----
function readHash() { const p = new URLSearchParams(location.hash.slice(1)); for (const d of DIMS) { sel[d.key] = new Set((p.get(d.key) || '').split(',').filter(x => x !== '').map(Number)); } }
function writeHash() { const p = new URLSearchParams(); for (const d of DIMS) if (sel[d.key].size) p.set(d.key, [...sel[d.key]].sort((a, b) => a - b).join(',')); history.replaceState(null, '', p.toString() ? '#' + p.toString() : location.pathname); }

// ---- パネル描画 ----
const panel = $('facets');
const chipEls = {};
for (const d of DIMS) {
  const box = document.createElement(d.collapsible ? 'details' : 'section'); box.className = 'facet';
  const head = document.createElement(d.collapsible ? 'summary' : 'div'); head.className = 'facet-head';
  const h = document.createElement('span'); h.className = 'facet-label'; h.textContent = d.label; head.appendChild(h);
  const badge = document.createElement('span'); badge.className = 'facet-sel'; head.appendChild(badge); d.badge = badge;
  if (d.help) { const s = document.createElement('span'); s.className = 'facet-help'; s.textContent = d.help; head.appendChild(s); }
  box.appendChild(head);
  const chips = document.createElement('div'); chips.className = 'chips'; box.appendChild(chips);
  chipEls[d.key] = D[d.key].map((name, i) => {
    if (d.skipZero && i === 0) return null;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; b.dataset.i = i;
    const t = document.createElement('span'); t.textContent = name; const n = document.createElement('span'); n.className = 'n';
    b.append(t, n); b.onclick = () => { sel[d.key].has(i) ? sel[d.key].delete(i) : sel[d.key].add(i); update(); };
    chips.appendChild(b); return b;
  });
  panel.appendChild(box);
}
$('reset').onclick = () => { for (const d of DIMS) sel[d.key].clear(); update(); };

// ---- 集計 ----
function facetCounts(d) {
  const cnt = new Array(D[d.key].length).fill(0);
  for (const r of R) { if (!passesAll(r, d)) continue; const v = r[d.col], c = r[9];
    if (d.bits) { for (let i = 0; i < cnt.length; i++) if (v & (1 << i)) cnt[i] += c; } else cnt[v] += c; }
  return cnt;
}
function update() {
  writeHash();
  const rows = R.filter(r => passesAll(r, null)); const total = rows.reduce((a, r) => a + r[9], 0);
  $('hero').textContent = fmt.format(total); $('hero-sub').textContent = `全体 ${fmt.format(cube.total)} 社の ${pct(total / cube.total)}`;
  const by = (col, n, mask) => { const a = new Array(n).fill(0); for (const r of rows) { if (mask) { for (let i = 0; i < n; i++) if (r[col] & (1 << i)) a[i] += r[9]; } else a[r[col]] += r[9]; } return a; };
  const st = by(3, 6); const alive = st[0] + st[5]; $('t-alive').textContent = fmt.format(alive); $('t-closed').textContent = fmt.format(total - alive);
  $('t-closed-sub').textContent = total ? pct((total - alive) / total) + ' が登記閉鎖' : '';
  const fl = by(5, 2, true); $('t-listed').textContent = fmt.format(st[5]); $('t-univ').textContent = fmt.format(fl[0]);
  // ファセットの件数
  for (const d of DIMS) {
    const cnt = facetCounts(d); const s = sel[d.key];
    chipEls[d.key].forEach((b, i) => { if (!b) return; b.querySelector('.n').textContent = fmt.format(cnt[i]); b.classList.toggle('on', s.has(i)); b.classList.toggle('zero', cnt[i] === 0 && !s.has(i)); });
    d.badge.textContent = s.size ? `${s.size} 選択` : '';
  }
  // 分布チャート
  const SL = ['存続', '清算結了', '合併で消滅', 'その他の閉鎖']; const SC = [C.s1, C.muted, C.s2, C.s8];
  const yearStatus = SL.map(() => new Array(D.year.length).fill(0));
  const sIdx = s => s === 5 ? 0 : Math.min(s, 3);
  for (const r of rows) yearStatus[sIdx(r[3])][r[0]] += r[9];
  stackedColumns($('x-year'), { categories: D.year.map((y, i) => i === D.year.length - 1 ? y + '*' : y), series: SL.map((n, i) => ({ name: n, color: SC[i], values: yearStatus[i] })), unit: '社' });
  const cyStatus = SL.slice(1).map(() => new Array(D.closed_year.length - 1).fill(0));
  for (const r of rows) if (r[4] > 0 && r[3] >= 1 && r[3] <= 4) cyStatus[Math.min(r[3], 3) - 1][r[4] - 1] += r[9];
  stackedColumns($('x-closed'), { categories: D.closed_year.slice(1).map((y, i, a) => i === a.length - 1 ? y + '*' : y), series: SL.slice(1).map((n, i) => ({ name: n, color: SC[i + 1], values: cyStatus[i] })), unit: '社' });
  const pr = by(1, D.pref.length).map((v, i) => ({ label: D.pref[i], value: v })).filter(x => x.value).sort((a, b) => b.value - a.value).slice(0, 15);
  hBars($('x-pref'), { items: pr.length ? pr : [{ label: '—', value: 0 }], color: C.s1, unit: '社' });
  const kwc = by(6, D.kw.length, true).map((v, i) => ({ label: D.kw[i], value: v })).filter(x => x.value).sort((a, b) => b.value - a.value);
  hBars($('x-kw'), { items: kwc.length ? kwc : [{ label: '—', value: 0 }], color: C.muted, unit: '社' });
  const jx = by(7, D.jpx.length).map((v, i) => ({ label: D.jpx[i], value: v })).filter((x, i) => i > 0 && x.value).sort((a, b) => b.value - a.value).slice(0, 12);
  $('x-jpx-card').classList.toggle('hidden', !jx.length); if (jx.length) hBars($('x-jpx'), { items: jx, color: C.s1, unit: '社' });
  const fx = by(8, D.field.length).map((v, i) => ({ label: D.field[i], value: v })).filter((x, i) => i > 0 && x.value).sort((a, b) => b.value - a.value).slice(0, 12);
  $('x-field-card').classList.toggle('hidden', !fx.length); if (fx.length) hBars($('x-field'), { items: fx, color: C.s3, unit: '社' });
  const kd = by(2, D.kind.length); $('x-kind-note').textContent = D.kind.map((k, i) => `${k} ${fmt.format(kd[i])}`).filter((_, i) => kd[i]).join(' / ');
}
readHash(); update(); window.addEventListener('hashchange', () => { readHash(); update(); });
