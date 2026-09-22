import { fmt, pct } from './charts.js';
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search); const id = params.get('id');
const meta = await (await fetch('data/meta.json')).json();
const cats = await (await fetch('data/categories/index.json')).json();
const STATUS = meta.status_codes;
const GROUPS = { exit: 'Exit・閉鎖の種類', attr: '属性', industry_jpx33: '上場企業の業種（EDINET）', field: '大学発ベンチャーの技術分野', keyword: '商号キーワードによる推定（精度低）' };

if (!id) {  // カテゴリ一覧
  $('cat-index').classList.remove('hidden');
  const wrap = $('groups');
  for (const g of Object.keys(GROUPS)) {
    const list = cats.filter(c => c.group === g).sort((a, b) => b.count - a.count); if (!list.length) continue;
    const card = document.createElement('div'); card.className = 'card'; const h = document.createElement('h3'); h.textContent = GROUPS[g]; card.appendChild(h);
    const ul = document.createElement('div'); ul.className = 'catlist';
    for (const c of list) { const a = document.createElement('a'); a.href = `category.html?id=${encodeURIComponent(c.id)}`; const s = document.createElement('span'); s.textContent = c.label; const n = document.createElement('span'); n.className = 'n'; n.textContent = fmt.format(c.count) + ' 社'; a.append(s, n); ul.appendChild(a); }
    card.appendChild(ul); wrap.appendChild(card);
  }
} else {
  const cat = cats.find(c => c.id === id); if (!cat) { $('title').textContent = 'カテゴリが見つかりません'; throw new Error('no category'); }
  $('cat-page').classList.remove('hidden');
  document.title = `${cat.label} | 日本の新設法人ライフサイクル`;
  $('title').textContent = cat.label;
  $('tier').textContent = cat.tier === 1 ? '公的コードで確定' : cat.tier === 2 ? '公的文書から推定' : '名称から推定';
  const st = cat.status; $('count').textContent = `${fmt.format(cat.count)} 社（存続 ${fmt.format(st.A || 0)} / 清算結了 ${fmt.format(st.L || 0)} / 合併消滅 ${fmt.format(st.M || 0)} / 登記官閉鎖 ${fmt.format((st.R || 0) + (st.O || 0))}）`;
  const extraHead = cat.group === 'exit' && cat.id === 'merged' ? '承継先' : cat.id === 'listed' ? '業種' : (cat.group === 'attr' || cat.group === 'field') ? '関連大学' : '備考';
  $('extra-head').textContent = extraHead;
  // 全ページを読んでクライアント側で絞り込み (1カテゴリ最大でも数MB)
  const rows = (await Promise.all(Array.from({ length: cat.pages }, (_, p) => fetch(`data/categories/${cat.id}/${p + 1}.json`).then(r => r.json())))).flat();
  const yearSel = $('f-year'), prefSel = $('f-pref'), stSel = $('f-status');
  for (const y of Array.from(new Set(rows.map(r => r[3]))).sort((a, b) => b - a)) yearSel.add(new Option(y + '年', y));
  for (const p of Array.from(new Set(rows.map(r => r[2]))).filter(Boolean).sort()) prefSel.add(new Option(p, p));
  for (const [k, v] of Object.entries(STATUS)) stSel.add(new Option(v, k));
  const PAGE = 100; let page = 1;
  const filtered = () => rows.filter(r => (!yearSel.value || String(r[3]) === yearSel.value) && (!prefSel.value || r[2] === prefSel.value) && (!stSel.value || r[4] === stSel.value));
  const render = () => {
    const f = filtered(); const pages = Math.max(1, Math.ceil(f.length / PAGE)); page = Math.min(page, pages);
    $('shown').textContent = `${fmt.format(f.length)} 社中 ${fmt.format(Math.min(f.length, (page - 1) * PAGE + 1))}〜${fmt.format(Math.min(f.length, page * PAGE))} 社を表示`;
    $('pg').textContent = `${page} / ${pages}`; $('prev').disabled = page <= 1; $('next').disabled = page >= pages;
    const tb = $('rows'); tb.textContent = '';
    for (const r of f.slice((page - 1) * PAGE, page * PAGE)) {
      const tr = document.createElement('tr');
      const cells = [String(r[1]).normalize('NFKC'), r[2], r[3] + '年', null, String(r[5] || '').normalize('NFKC'), r[0]];
      cells.forEach((c, i) => { const td = document.createElement('td'); if (i === 3) { const dot = document.createElement('span'); dot.className = 'status ' + r[4]; td.appendChild(dot); td.appendChild(document.createTextNode(STATUS[r[4]] || r[4])); } else if (i === 5) { const a = document.createElement('a'); a.href = `https://www.houjin-bangou.nta.go.jp/henkorireki-johoto.html?selHouzinNo=${c}`; a.target = '_blank'; a.rel = 'noopener'; a.textContent = c; a.title = '国税庁 法人番号公表サイトで見る'; td.appendChild(a); } else td.textContent = c; tr.appendChild(td); });
      tb.appendChild(tr);
    }
  };
  [yearSel, prefSel, stSel].forEach(s => s.addEventListener('change', () => { page = 1; render(); }));
  $('prev').onclick = () => { page--; render(); }; $('next').onclick = () => { page++; render(); };
  render();
}
