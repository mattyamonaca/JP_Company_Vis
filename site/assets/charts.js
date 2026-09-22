// 軽量SVGチャート (依存なし)。細いマーク・ヘアラインのグリッド・ホバーのツールチップ・表ビューを共通で持つ。
const NS = 'http://www.w3.org/2000/svg';
export const fmt = new Intl.NumberFormat('ja-JP');
export const pct = v => (v * 100).toFixed(1) + '%';
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const div = (cls, parent, text) => { const d = document.createElement('div'); if (cls) d.className = cls; if (text != null) d.textContent = text; if (parent) parent.appendChild(d); return d; };
const niceMax = v => { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const n = v / p; const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10; return m * p; };
const ticks = (max, n = 4) => Array.from({ length: n + 1 }, (_, i) => max * i / n);

function frame(container) {
  container.textContent = '';
  const chart = div('chart', container); const tools = div('tools', container);
  const tbl = div('tableview hidden', container);
  const btn = document.createElement('button'); btn.className = 'ghost'; btn.type = 'button'; btn.textContent = '表で見る';
  btn.onclick = () => { const show = tbl.classList.toggle('hidden'); chart.classList.toggle('hidden', !show); btn.textContent = show ? '表で見る' : 'グラフで見る'; };
  tools.appendChild(btn);
  return { chart, tbl };
}
function legend(parent, series, kind = 'rect') {
  if (series.length < 2) return;
  const lg = div('legend'); parent.prepend(lg);
  for (const s of series) { const sp = document.createElement('span'); const i = document.createElement('i'); i.className = kind; i.style.background = s.color; sp.appendChild(i); sp.appendChild(document.createTextNode(s.name)); lg.appendChild(sp); }
}
function table(tbl, head, rows) {
  tbl.textContent = ''; const t = document.createElement('table'); t.className = 'data';
  const tr = document.createElement('tr'); head.forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; if (i > 0) th.className = 'n'; tr.appendChild(th); }); t.appendChild(tr);
  for (const r of rows) { const tr2 = document.createElement('tr'); r.forEach((c, i) => { const td = document.createElement('td'); td.textContent = typeof c === 'number' ? fmt.format(c) : c; if (i > 0) td.className = 'n'; tr2.appendChild(td); }); t.appendChild(tr2); }
  tbl.appendChild(t);
}
function tooltip(chart) {
  const tip = div('tip hidden', chart);
  return {
    show(x, y, title, rows) {
      tip.textContent = ''; div('t', tip, title);
      for (const r of rows) { const line = div('r', tip); const k = document.createElement('span'); k.className = 'k'; k.style.background = r.color || 'transparent'; const name = document.createElement('span'); name.textContent = r.name; name.style.flex = '1'; const b = document.createElement('b'); b.textContent = r.value; line.append(k, name, b); }
      tip.classList.remove('hidden');
      const cw = chart.clientWidth, tw = tip.offsetWidth; tip.style.left = Math.min(Math.max(0, x - tw / 2), cw - tw) + 'px'; tip.style.top = Math.max(0, y - tip.offsetHeight - 12) + 'px';
    },
    hide() { tip.classList.add('hidden'); }
  };
}
const observe = (container, render) => { let w = 0; const ro = new ResizeObserver(() => { const nw = container.clientWidth; if (nw && Math.abs(nw - w) > 8) { w = nw; render(); } }); ro.observe(container); };

// 積み上げ縦棒: categories(x) × series
export function stackedColumns(container, { categories, series, unit = '', valueFmt = fmt.format, note }) {
  const { chart, tbl } = frame(container);
  table(tbl, ['', ...series.map(s => s.name), series.length > 1 ? '合計' : null].filter(Boolean),
    categories.map((c, i) => [c, ...series.map(s => s.values[i] || 0), ...(series.length > 1 ? [series.reduce((a, s) => a + (s.values[i] || 0), 0)] : [])]));
  const render = () => {
    chart.textContent = ''; legend(chart, series);
    const W = chart.clientWidth || 600, H = 260, L = 52, R = 12, T = 12, B = 34, pw = W - L - R, ph = H - T - B;
    const totals = categories.map((_, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0));
    const ymax = niceMax(Math.max(...totals)); const y = v => T + ph - v / ymax * ph;
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}` }, chart); const g = el('g', { class: 'grid' }, svg);
    for (const t of ticks(ymax)) { el('line', { x1: L, x2: W - R, y1: y(t), y2: y(t) }, g); el('text', { x: L - 6, y: y(t) + 4, 'text-anchor': 'end' }, svg).textContent = valueFmt(t); }
    el('line', { x1: L, x2: W - R, y1: y(0), y2: y(0), class: 'baseline' }, svg);
    const band = pw / categories.length, bw = Math.min(24, band * 0.6); const tip = tooltip(chart);
    categories.forEach((c, i) => {
      const x = L + band * i + (band - bw) / 2; let acc = 0; const gcol = el('g', { class: 'mark' }, svg);
      series.forEach((s, k) => {
        const v = s.values[i] || 0; if (!v) return; const y1 = y(acc + v), y0 = y(acc); acc += v;
        const top = acc === totals[i]; const h = Math.max(0, y0 - y1 - (k > 0 ? 2 : 0));
        const r = top ? 4 : 0; const yy = y1 + (k > 0 ? 2 : 0);
        // 上端だけ丸める path
        const d = r ? `M${x},${yy + h}V${yy + r}Q${x},${yy} ${x + r},${yy}H${x + bw - r}Q${x + bw},${yy} ${x + bw},${yy + r}V${yy + h}Z` : `M${x},${yy}h${bw}v${h}h${-bw}Z`;
        el('path', { d, fill: s.color }, gcol);
      });
      const lstep = Math.max(1, Math.ceil(36 / band));
      if (i % lstep === 0 || i === categories.length - 1) { const lab = el('text', { x: x + bw / 2, y: H - B + 16, 'text-anchor': 'middle' }, svg); lab.textContent = c; }
      const hit = el('rect', { x: L + band * i, y: T, width: band, height: ph + B - 10, class: 'hit' }, svg);
      const show = () => { gcol.classList.add('on'); tip.show(x + bw / 2, y(totals[i]), c + (note && note[i] ? note[i] : ''), [...series.map(s => ({ name: s.name, color: s.color, value: valueFmt(s.values[i] || 0) + unit })), ...(series.length > 1 ? [{ name: '合計', value: valueFmt(totals[i]) + unit }] : [])]); };
      const hide = () => { gcol.classList.remove('on'); tip.hide(); };
      hit.addEventListener('pointermove', show); hit.addEventListener('pointerleave', hide); hit.setAttribute('tabindex', '0'); hit.addEventListener('focus', show); hit.addEventListener('blur', hide);
    });
  };
  render(); observe(container, render);
}

// 横棒 (1系列)
export function hBars(container, { items, color, unit = '', valueFmt = fmt.format, subLabel }) {
  const { chart, tbl } = frame(container);
  table(tbl, ['', unit || '件', ...(subLabel ? [subLabel] : [])], items.map(it => [it.label, it.value, ...(subLabel ? [it.sub] : [])]));
  const render = () => {
    chart.textContent = '';
    const W = chart.clientWidth || 600, row = 26, L = Math.min(200, Math.max(90, W * 0.32)), R = 64, T = 6, H = T + items.length * row + 8;
    const max = niceMax(Math.max(...items.map(i => i.value))); const pw = W - L - R; const svg = el('svg', { viewBox: `0 0 ${W} ${H}` }, chart); const tip = tooltip(chart);
    el('line', { x1: L, x2: L, y1: T, y2: H - 8, class: 'baseline' }, svg);
    items.forEach((it, i) => {
      const yy = T + i * row + (row - 16) / 2, w = Math.max(0, it.value / max * pw), r = Math.min(4, w);
      const lab = el('text', { x: L - 8, y: yy + 12, 'text-anchor': 'end', class: 'lbl' }, svg); const nl = String(it.label).normalize('NFKC'); const mc = Math.max(6, Math.floor((L - 10) / 12)); lab.textContent = nl.length > mc ? nl.slice(0, mc - 1) + '…' : nl;
      const bar = el('path', { d: `M${L},${yy}H${L + w - r}Q${L + w},${yy} ${L + w},${yy + r}V${yy + 16 - r}Q${L + w},${yy + 16} ${L + w - r},${yy + 16}H${L}Z`, fill: color, class: 'mark' }, svg);
      const val = el('text', { x: L + w + 6, y: yy + 12 }, svg); val.textContent = valueFmt(it.value) + (it.suffix || '');
      const hit = el('rect', { x: 0, y: T + i * row, width: W, height: row, class: 'hit', tabindex: '0' }, svg);
      const show = () => { bar.classList.add('on'); tip.show(L + w / 2, yy, it.label, [{ name: unit || '件数', color, value: valueFmt(it.value) }, ...(it.sub != null ? [{ name: subLabel || '', value: it.sub }] : [])]); };
      const hide = () => { bar.classList.remove('on'); tip.hide(); };
      hit.addEventListener('pointermove', show); hit.addEventListener('pointerleave', hide); hit.addEventListener('focus', show); hit.addEventListener('blur', hide);
    });
  };
  render(); observe(container, render);
}

// 折れ線 (複数系列、クロスヘア)
export function lines(container, { x, series, yFmt = v => v, xFmt = v => String(v), yMin = null, yMax = null, endLabels = [] }) {
  const { chart, tbl } = frame(container);
  table(tbl, ['', ...series.map(s => s.name)], x.map((xv, i) => [xFmt(xv), ...series.map(s => s.values[i] == null ? '—' : yFmt(s.values[i]))]));
  const render = () => {
    chart.textContent = ''; legend(chart, series, 'line');
    const W = chart.clientWidth || 600, H = 280, L = 52, R = 48, T = 12, B = 34, pw = W - L - R, ph = H - T - B;
    const all = series.flatMap(s => s.values.filter(v => v != null));
    const lo = yMin ?? Math.min(...all), hi = yMax ?? niceMax(Math.max(...all));
    const xs = i => L + (x.length > 1 ? i / (x.length - 1) * pw : pw / 2), ys = v => T + ph - (v - lo) / (hi - lo) * ph;
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}` }, chart); const g = el('g', { class: 'grid' }, svg);
    for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; el('line', { x1: L, x2: W - R, y1: ys(v), y2: ys(v) }, g); el('text', { x: L - 6, y: ys(v) + 4, 'text-anchor': 'end' }, svg).textContent = yFmt(v); }
    el('line', { x1: L, x2: W - R, y1: ys(lo), y2: ys(lo), class: 'baseline' }, svg);
    const step = Math.max(1, Math.ceil(x.length / Math.floor(pw / 56)));
    x.forEach((xv, i) => { if (i % step === 0 || i === x.length - 1) el('text', { x: xs(i), y: H - B + 16, 'text-anchor': 'middle' }, svg).textContent = xFmt(xv); });
    series.forEach(s => {
      let d = ''; s.values.forEach((v, i) => { if (v == null) return; d += (d ? 'L' : 'M') + xs(i) + ',' + ys(v); });
      el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
      const last = s.values.map((v, i) => [v, i]).filter(p => p[0] != null).pop();
      if (last && endLabels.includes(s.name)) { el('circle', { cx: xs(last[1]), cy: ys(last[0]), r: 4, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2 }, svg); el('text', { x: xs(last[1]) + 8, y: ys(last[0]) + 4, class: 'lbl' }, svg).textContent = s.name; }
    });
    const cross = el('line', { x1: 0, x2: 0, y1: T, y2: T + ph, stroke: 'var(--axis)', 'stroke-width': 1, class: 'hidden' }, svg); const dots = el('g', {}, svg); const tip = tooltip(chart);
    const hit = el('rect', { x: L, y: T, width: pw, height: ph, class: 'hit' }, svg);
    hit.addEventListener('pointermove', ev => {
      const pt = svg.getBoundingClientRect(); const px = (ev.clientX - pt.left) * W / pt.width; const i = Math.max(0, Math.min(x.length - 1, Math.round((px - L) / pw * (x.length - 1))));
      cross.classList.remove('hidden'); cross.setAttribute('x1', xs(i)); cross.setAttribute('x2', xs(i)); dots.textContent = '';
      series.forEach(s => { if (s.values[i] != null) el('circle', { cx: xs(i), cy: ys(s.values[i]), r: 4, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2 }, dots); });
      tip.show(xs(i) * pt.width / W, T, xFmt(x[i]), series.filter(s => s.values[i] != null).map(s => ({ name: s.name, color: s.color, value: yFmt(s.values[i]) })));
    });
    hit.addEventListener('pointerleave', () => { cross.classList.add('hidden'); dots.textContent = ''; tip.hide(); });
  };
  render(); observe(container, render);
}
