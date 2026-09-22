// 次元ノードを配置して左から順に絞り込む探索ボード (cube.json をブラウザ側で集計)
import { fmt } from './charts.js';
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (v, d = 1) => (v * 100).toFixed(d) + '%';
const cube = await (await fetch('data/cube.json')).json();
const cats = await (await fetch('data/categories/index.json')).json().catch(() => []);
const D = cube.dims, R = cube.rows, TOTAL = cube.total;
// 行: 0 year,1 pref,2 kind,3 status,4 closed_year,5 flags(bits),6 kw(bits),7 jpx,8 field,9 count
const DIMS = [
  { key: 'year', col: 0, label: '設立年', agg: '全設立年', def: '法人番号の指定年（国税庁 法人番号公表サイト）。設立登記の数日後に指定される。2026年は8月末まで。' },
  { key: 'kind', col: 2, label: '法人種別', agg: '全種別', def: '法人番号データの法人種別。有限会社は2006年以降新設できないため、組織変更・復活分。' },
  { key: 'status', col: 3, label: '出口', agg: '出口を問わず', def: '登記記録の閉鎖事由（国税庁）と、EDINETの上場区分・書類履歴（金融庁）から判定。「出口なし」は登記が閉鎖されておらず上場歴もない会社で、休眠を含む。' },
  { key: 'flags', col: 5, label: '属性・イベント', agg: '属性を問わず', bits: true, def: '大学発＝経産省 大学発ベンチャーDB掲載。他社を吸収＝合併の承継先になった会社。上場した＝新規公開時の有価証券届出書か証券コード付き有価証券報告書あり。TOB＝公開買付届出書の対象（2021年9月以降）。上場企業に買収された＝買い手の有価証券報告書の企業結合注記に被取得企業として記載（重要性のある案件のみ）。' },
  { key: 'pref', col: 1, label: '都道府県', agg: '全国', def: '本店所在地の都道府県（法人番号データ、2026年8月末時点）。' },
  { key: 'closed_year', col: 4, label: '閉鎖年', agg: '閉鎖年を問わず', def: '登記記録が閉鎖された年。「閉鎖なし」は現存する会社。' },
  { key: 'kw', col: 6, label: '商号キーワード', agg: 'キーワードを問わず', bits: true, def: '商号に含まれる語からの推定。名称に業種を示す語がある会社（約17%）にしか付かず、精度は低い。' },
  { key: 'jpx', col: 7, label: '上場業種', agg: '業種を問わず', skipZero: true, def: 'EDINETコードリストの提出者業種（33業種）。現在上場している会社にだけ付く。' },
  { key: 'field', col: 8, label: '技術分野', agg: '分野を問わず', skipZero: true, def: '経産省 大学発ベンチャーDBの主力製品・サービス関連技術分野。大学発ベンチャーにだけ付く。' },
];
const BY = Object.fromEntries(DIMS.map(d => [d.key, d]));
const S = { sel: {}, skip: {}, open: {}, order: [], focus: { dim: null, id: null } };
DIMS.forEach(d => { S.sel[d.key] = null; S.skip[d.key] = false; S.open[d.key] = false; });

// ---------- 集計 ----------
const placed = () => S.order.map(k => BY[k]);
function matches(r, d) { const v = S.sel[d.key]; if (v === null) return true; return d.bits ? (r[d.col] & (1 << v)) !== 0 : r[d.col] === v; }
function filterBefore(d) { const P = placed(); const upto = d ? P.slice(0, P.indexOf(d)) : P; return R.filter(r => upto.every(x => matches(r, x))); }
function counts(rows, d) { const n = new Array(D[d.key].length).fill(0); for (const r of rows) { const v = r[d.col], c = r[9]; if (d.bits) { for (let i = 0; i < n.length; i++) if (v & (1 << i)) n[i] += c; } else n[v] += c; } return n; }
const sum = a => a.reduce((x, y) => x + y, 0);
function optName(d, i) { return D[d.key][i]; }

// ---------- URL ----------
function readHash() { const p = new URLSearchParams(location.hash.slice(1)); const cols = (p.get('cols') || '').split(',').filter(k => BY[k]); S.order = [...new Set(cols)]; DIMS.forEach(d => { S.open[d.key] = S.order.includes(d.key); const v = p.get(d.key); S.sel[d.key] = v != null && v !== '' && v !== 'all' ? +v : null; S.skip[d.key] = v === 'all'; }); }
function writeHash() { const p = new URLSearchParams(); const cols = placed().map(d => d.key); if (cols.length) p.set('cols', cols.join(',')); DIMS.forEach(d => { if (S.sel[d.key] !== null) p.set(d.key, S.sel[d.key]); else if (S.skip[d.key]) p.set(d.key, 'all'); }); const h = p.toString(); history.replaceState(null, '', h ? '#' + h : location.pathname); }

// ---------- DOM 構築 ----------
const palette = $('palette'), board = $('board');
for (const d of DIMS) {
  const b = document.createElement('button'); b.className = 'pnode dim-' + d.key; b.dataset.dim = d.key;
  b.innerHTML = `<span class="c">${D[d.key].length - (d.skipZero ? 1 : 0)}</span><span class="t">${esc(d.label)}<span class="s" id="pn-${d.key}">未配置</span></span>`;
  b.addEventListener('click', () => { if (S.open[d.key]) unplace(d); else place(d); renderAll(); });
  palette.appendChild(b);
  const col = document.createElement('div'); col.className = 'col dim-' + d.key; col.dataset.dim = d.key; col.hidden = true;
  col.innerHTML = `<div class="hubwrap"><button class="hubx" title="外す" aria-label="${esc(d.label)} を外す">×</button><button class="hub" aria-expanded="false">${esc(d.label)}<small>${D[d.key].length - (d.skipZero ? 1 : 0)}</small></button><div class="hubcap" id="cap-${d.key}"></div></div><div class="list" id="list-${d.key}"></div>`;
  col.querySelector('.hubx').addEventListener('click', ev => { ev.stopPropagation(); unplace(d); renderAll(); });
  col.querySelector('.hub').addEventListener('click', () => { S.focus = { dim: d.key, id: 'hub' }; renderAll(); });
  const L = col.querySelector('.list');
  L.addEventListener('click', ev => { const b = ev.target.closest('.row'); if (!b) return; select(d, b.dataset.id); });
  L.addEventListener('scroll', () => requestAnimationFrame(drawEdges), { passive: true });
  L.addEventListener('mouseover', ev => { const b = ev.target.closest('.row'); if (!b) return; const p = document.querySelector(`.edges path.fan[data-e="fan:${d.key}:${b.dataset.id}"]`); if (p) p.classList.add('hot'); });
  L.addEventListener('mouseout', ev => { const b = ev.target.closest('.row'); if (!b) return; const p = document.querySelector(`.edges path.fan[data-e="fan:${d.key}:${b.dataset.id}"]`); if (p) p.classList.remove('hot'); });
  board.appendChild(col);
}
function place(d) { S.open[d.key] = true; S.order = S.order.filter(k => k !== d.key); S.order.push(d.key); S.focus = { dim: d.key, id: 'hub' }; }
function unplace(d) { S.sel[d.key] = null; S.skip[d.key] = false; S.open[d.key] = false; S.order = S.order.filter(k => k !== d.key); if (S.focus.dim === d.key) S.focus = { dim: null, id: null }; }
function select(d, id) {
  if (id === 'all') { S.sel[d.key] = null; S.skip[d.key] = true; S.focus = { dim: d.key, id: 'all' }; }
  else { const v = +id; if (S.sel[d.key] === v) { S.sel[d.key] = null; S.focus = { dim: d.key, id: 'hub' }; } else { S.sel[d.key] = v; S.skip[d.key] = false; S.focus = { dim: d.key, id: v }; } }
  renderAll();
}
const isFocus = (d, id) => S.focus.dim === d.key && String(S.focus.id) === String(id);

// ---------- 列 ----------
function renderCol(d) {
  const col = board.querySelector(`.col[data-dim="${d.key}"]`); col.hidden = !S.open[d.key]; if (!S.open[d.key]) return;
  const rows = filterBefore(d), n = counts(rows, d), tot = sum(rows.map(r => r[9]));
  const max = Math.max(1, ...n.filter((_, i) => !(d.skipZero && i === 0)));
  let html = `<button class="row skip${S.skip[d.key] ? ' sel' : ''}${isFocus(d, 'all') ? ' focus' : ''}" data-id="all"><span class="dot"></span><span class="nm">${esc(d.agg)}でまとめる</span><span class="arr">→</span></button>`;
  html += `<div class="grp">${esc(condName(d))}　${fmt.format(tot)} 社の内訳</div>`;
  const order = D[d.key].map((_, i) => i);
  if (d.key === 'pref' || d.key === 'jpx' || d.key === 'field' || d.key === 'kw') order.sort((a, b) => n[b] - n[a]);
  for (const i of order) {
    if (d.skipZero && i === 0) continue;
    const sel = S.sel[d.key] === i;
    html += `<button class="row${sel ? ' sel' : ''}${isFocus(d, i) ? ' focus' : ''}${n[i] === 0 ? ' zero' : ''}" data-id="${i}" role="option" aria-selected="${sel}"><span class="dot"></span><span class="nm">${esc(optName(d, i))}</span><span class="bar"><i style="width:${(n[i] / max * 100).toFixed(1)}%"></i></span><span class="v">${fmt.format(n[i])}<small>${tot ? pct(n[i] / tot) : '–'}</small></span></button>`;
  }
  if (d.skipZero) html += `<div class="grp">該当なし ${fmt.format(n[0])} 社</div>`;
  $('list-' + d.key).innerHTML = html;
  const cap = $('cap-' + d.key);
  cap.innerHTML = S.sel[d.key] !== null ? `<b>${esc(optName(d, S.sel[d.key]))}</b>` : S.skip[d.key] ? `<b>${esc(d.agg)}</b>（まとめ）` : `${fmt.format(tot)} 社`;
  col.querySelector('.hub').classList.toggle('focus', isFocus(d, 'hub'));
}
function condName(d) { const P = placed().slice(0, placed().indexOf(d)); const parts = P.filter(x => S.sel[x.key] !== null).map(x => optName(x, S.sel[x.key])); return parts.length ? parts.join('・') : '全社'; }

// ---------- パレット・パンくず ----------
function renderPalette() {
  for (const d of DIMS) { const b = palette.querySelector(`.pnode[data-dim="${d.key}"]`); b.classList.toggle('on', S.open[d.key]); $('pn-' + d.key).textContent = !S.open[d.key] ? '未配置（合算）' : S.sel[d.key] !== null ? optName(d, S.sel[d.key]) : S.skip[d.key] ? d.agg + '（まとめ）' : d.agg; }
  $('board-empty').hidden = placed().length > 0;
}
function renderCrumb() {
  let h = `<button data-lv="0" style="--sw:var(--muted)">全社 ${fmt.format(TOTAL)}</button>`;
  placed().forEach((d, i) => { if (S.sel[d.key] !== null) h += `<span class="sep">›</span><button data-lv="${i + 1}" style="--sw:var(--d-${d.key === 'closed_year' ? 'closed' : d.key})"><span class="chipdot"></span>${esc(optName(d, S.sel[d.key]))}</button>`; else if (S.skip[d.key]) h += `<span class="sep">›</span><button data-lv="${i + 1}" class="skip" style="--sw:var(--d-${d.key === 'closed_year' ? 'closed' : d.key})">${esc(d.agg)}</button>`; });
  $('crumb').innerHTML = h;
}
$('crumb').addEventListener('click', ev => { const b = ev.target.closest('button'); if (!b) return; const lv = +b.dataset.lv; placed().forEach((d, i) => { if (i >= lv) { S.sel[d.key] = null; S.skip[d.key] = false; } }); S.focus = { dim: null, id: null }; renderAll(); });

// ---------- パネル ----------
function catFor(d, id) {
  const find = (group, label) => cats.find(c => c.group === group && (label == null || c.label === label));
  let c = null;
  if (d.key === 'status') c = { 1: find('exit', '清算して閉鎖した'), 2: find('exit', '合併で消滅した'), 5: find('exit', '上場している'), 6: find('exit', '上場した') }[id];
  else if (d.key === 'flags') c = [find('attr', '大学発ベンチャー'), find('exit', '他社を吸収した（合併の承継先）'), find('exit', '上場した'), find('exit', 'TOB（公開買付）の対象になった'), find('exit', '上場企業に買収された（株式取得）')][id];
  else if (d.key === 'kw') c = find('keyword', optName(d, id)); else if (d.key === 'jpx') c = find('industry_jpx33', optName(d, id)); else if (d.key === 'field') c = find('field', optName(d, id));
  if (!c) return null;
  const q = new URLSearchParams({ id: c.id }); const P = placed();
  const y = S.sel.year, p = S.sel.pref, st = S.sel.status;
  if (y !== null && P.some(x => x.key === 'year')) q.set('year', D.year[y]); if (p !== null && P.some(x => x.key === 'pref')) q.set('pref', D.pref[p]);
  if (st !== null && d.key !== 'status') { const code = { 0: 'A', 1: 'L', 2: 'M', 3: 'R', 4: 'O', 5: 'A', 6: 'A' }[st]; if (code) q.set('status', code); }
  return 'category.html?' + q.toString();
}
function renderPanel() {
  const P = $('panel'); const f = S.focus; const all = filterBefore(null), allN = sum(all.map(r => r[9]));
  const dimVar = k => `var(--d-${k === 'closed_year' ? 'closed' : k})`;
  if (!f.dim) {
    P.style.setProperty('--sw', 'var(--line-strong)');
    P.innerHTML = `<span class="eyebrow">現在の条件</span><h2>${esc(placed().filter(d => S.sel[d.key] !== null).map(d => optName(d, S.sel[d.key])).join('・') || '全社')}</h2><div class="big">${fmt.format(allN)}<small>社 / ${pct(allN / TOTAL)}</small></div>${miniAll()}<p class="note">左のノードを置くと列が並び、行を選ぶと右隣の列がその条件の内訳になります。</p>`; return;
  }
  const d = BY[f.dim]; P.style.setProperty('--sw', dimVar(d.key)); P.style.setProperty('--soft', `var(--d-${d.key === 'closed_year' ? 'closed' : d.key}-soft)`);
  const rows = filterBefore(d), tot = sum(rows.map(r => r[9])), n = counts(rows, d);
  const pathHtml = `<div class="path">${placed().slice(0, placed().indexOf(d)).map(x => S.sel[x.key] !== null ? `<span style="--sw:${dimVar(x.key)}"><i></i>${esc(optName(x, S.sel[x.key]))}</span>` : S.skip[x.key] ? `<span style="--sw:${dimVar(x.key)}">${esc(x.agg)}</span>` : '').join('')}</div>`;
  if (f.id === 'hub' || f.id === 'all') {
    const top = D[d.key].map((nm, i) => [nm, n[i], i]).filter(x => !(d.skipZero && x[2] === 0)).sort((a, b) => b[1] - a[1]).slice(0, 10); const mx = Math.max(1, ...top.map(x => x[1]));
    P.innerHTML = `<span class="eyebrow">${esc(d.label)}</span><h2>${esc(f.id === 'all' ? d.agg + 'でまとめる' : condName(d))}</h2><div class="big">${fmt.format(tot)}<small>社 / ${pct(tot / TOTAL)}</small></div>${pathHtml}<h3>内訳（上位）</h3><div class="mini">${top.map(x => `<span class="l">${esc(x[0])}</span><span class="b"><i style="width:${(x[1] / mx * 100).toFixed(1)}%"></i></span><span class="n">${fmt.format(x[1])}</span>`).join('')}</div><h3>定義</h3><p>${esc(d.def)}</p>`; return;
  }
  const i = +f.id, v = n[i], nm = optName(d, i); const link = catFor(d, i);
  P.innerHTML = `<span class="eyebrow">${esc(d.label)}</span><h2>${esc(nm)}</h2><div class="big">${fmt.format(v)}<small>社</small></div>${pathHtml}<dl><dt>${esc(condName(d))} の中で</dt><dd>${tot ? pct(v / tot, 2) : '–'}</dd><dt>全社の中で</dt><dd>${pct(v / TOTAL, 2)}</dd><dt>分母</dt><dd>${fmt.format(tot)} 社</dd></dl>${nextDims(d, i)}${link ? `<a class="action" href="${link}">この条件の企業一覧 →</a>` : ''}<h3>定義</h3><p>${esc(d.def)}</p>`;
}
function nextDims(d, i) {
  // 選んだ行の内訳を、未配置の主要次元で簡易表示
  const rows = filterBefore(d).filter(r => matches(r, { ...d, key: d.key }) || true).filter(r => d.bits ? (r[d.col] & (1 << i)) !== 0 : r[d.col] === i);
  const show = DIMS.filter(x => !S.open[x.key] && ['status', 'kind', 'year', 'pref'].includes(x.key)).slice(0, 2);
  if (!show.length) return '';
  return show.map(x => { const n = counts(rows, x); const top = D[x.key].map((nm, k) => [nm, n[k]]).filter(t => t[1]).sort((a, b) => b[1] - a[1]).slice(0, 6); const mx = Math.max(1, ...top.map(t => t[1])); return `<h3>${esc(x.label)}別</h3><div class="mini" style="--sw:var(--d-${x.key === 'closed_year' ? 'closed' : x.key})">${top.map(t => `<span class="l">${esc(t[0])}</span><span class="b"><i style="width:${(t[1] / mx * 100).toFixed(1)}%"></i></span><span class="n">${fmt.format(t[1])}</span>`).join('')}</div>`; }).join('');
}
function miniAll() {
  const all = filterBefore(null); const parts = [];
  for (const k of ['status', 'kind']) { const d = BY[k]; const n = counts(all, d); const top = D[k].map((nm, i) => [nm, n[i]]).filter(t => t[1]).sort((a, b) => b[1] - a[1]).slice(0, 7); const mx = Math.max(1, ...top.map(t => t[1])); parts.push(`<h3>${esc(d.label)}</h3><div class="mini" style="--sw:var(--d-${k})">${top.map(t => `<span class="l">${esc(t[0])}</span><span class="b"><i style="width:${(t[1] / mx * 100).toFixed(1)}%"></i></span><span class="n">${fmt.format(t[1])}</span>`).join('')}</div>`); }
  return parts.join('');
}

// ---------- エッジ ----------
function drawEdges() {
  const svg = $('edges'), br = board.getBoundingClientRect(); svg.setAttribute('viewBox', `0 0 ${br.width} ${br.height}`);
  const rel = r => ({ l: r.left - br.left, r: r.right - br.left, t: r.top - br.top, b: r.bottom - br.top, cy: (r.top + r.bottom) / 2 - br.top });
  const hubRect = d => rel(board.querySelector(`.col[data-dim="${d.key}"] .hub`).getBoundingClientRect());
  const curve = (x1, y1, x2, y2) => { const dx = (x2 - x1) * 0.5; return `M${x1.toFixed(1)},${y1.toFixed(1)} C${(x1 + dx).toFixed(1)},${y1.toFixed(1)} ${(x2 - dx).toFixed(1)},${y2.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`; };
  const P = placed(); if (!P.length) { svg.innerHTML = ''; return; }
  const out = [];
  for (let i = 0; i < P.length - 1; i++) { const A = hubRect(P[i]), B = hubRect(P[i + 1]); out.push(`<path class="chain" d="${curve(A.r, A.cy, B.l, B.cy)}"/>`); }
  for (let i = 1; i < P.length; i++) {
    const d = P[i], src = P[i - 1]; const list = $('list-' + d.key), lr = rel(list.getBoundingClientRect());
    const sid = S.sel[src.key] !== null ? S.sel[src.key] : S.skip[src.key] ? 'all' : null; let s = null;
    if (sid !== null) { const el = document.querySelector(`#list-${src.key} .row[data-id="${sid}"]`); if (el) { const er = rel(el.getBoundingClientRect()), l0 = rel($('list-' + src.key).getBoundingClientRect()); s = (er.cy >= l0.t && er.cy <= l0.b) ? { x: er.r - 4, y: er.cy } : { x: l0.r, y: Math.max(l0.t, Math.min(l0.b, er.cy)) }; } }
    if (!s) { const hr = hubRect(src); s = { x: hr.r, y: hr.cy }; }
    const rows = list.querySelectorAll('.row'); const shares = [...rows].map(r => { const bi = r.querySelector('.bar i'); return bi ? parseFloat(bi.style.width) || 0 : 0; }); const mw = Math.max(1, ...shares);
    rows.forEach((r, k) => { const rr = rel(r.getBoundingClientRect()); if (rr.cy < lr.t + 6 || rr.cy > lr.b - 6) return; const sw = 1 + 5 * shares[k] / mw; out.push(`<path class="fan${S.sel[d.key] !== null && String(S.sel[d.key]) === r.dataset.id ? ' sel' : ''}" data-e="fan:${d.key}:${r.dataset.id}" style="--sw:var(--d-${d.key === 'closed_year' ? 'closed' : d.key})" stroke-width="${sw.toFixed(1)}" d="${curve(s.x, s.y, rr.l + 8, rr.cy)}"/>`); });
  }
  svg.innerHTML = out.join('');
}

function renderAll() { writeHash(); DIMS.forEach(renderCol); placed().forEach(d => board.appendChild(board.querySelector(`.col[data-dim="${d.key}"]`))); renderPalette(); renderCrumb(); renderPanel(); requestAnimationFrame(drawEdges); }
window.addEventListener('resize', () => requestAnimationFrame(drawEdges));
window.addEventListener('hashchange', () => { readHash(); renderAll(); });
// phone: bottom sheet
(function () {
  const mq = window.matchMedia('(max-width:640px)'), bar = $('sheetbar'), P = $('panel'); let last = '';
  const setOpen = o => { document.body.classList.toggle('sheet-open', o); bar.setAttribute('aria-expanded', o ? 'true' : 'false'); $('sheetbar-x').textContent = o ? '閉じる' : '開く'; };
  bar.addEventListener('click', () => setOpen(!document.body.classList.contains('sheet-open')));
  new MutationObserver(() => { if (P.innerHTML === last) return; last = P.innerHTML; const h = P.querySelector('h2'), e = P.querySelector('.eyebrow'); $('sheetbar-t').innerHTML = (e ? `<span class="eyebrow">${esc(e.textContent)}</span>　` : '') + `<b>${esc(h ? h.textContent : '')}</b>`; if (mq.matches && S.focus.dim) { setOpen(true); P.scrollTop = 0; } }).observe(P, { childList: true });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') setOpen(false); });
})();
readHash(); if (!placed().length && !location.hash) { S.order = ['year', 'status']; S.open.year = true; S.open.status = true; }
renderAll();
