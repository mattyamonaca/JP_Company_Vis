import { stackedColumns, hBars, lines, fmt, pct } from './charts.js';
const C = { s1: 'var(--s1)', s2: 'var(--s2)', s3: 'var(--s3)', s8: 'var(--s8)', muted: 'var(--deemph)' };
const SEQ = ['var(--seq-250)', 'var(--seq-300)', 'var(--seq-350)', 'var(--seq-400)', 'var(--seq-450)', 'var(--seq-500)', 'var(--seq-550)', 'var(--seq-600)'];
const $ = id => document.getElementById(id);
const sum = a => a.reduce((x, y) => x + (y || 0), 0);
const S = await (await fetch('data/summary.json')).json();
const cats = await (await fetch('data/categories/index.json')).json();
const catId = (group, label) => { const c = cats.find(c => c.group === group && (label == null || c.label === label)); return c ? `category.html?id=${encodeURIComponent(c.id)}` : null; };
const years = S.years, partial = years[years.length - 1];
const snap = S.snapshot_date; document.querySelectorAll('.snap').forEach(e => e.textContent = snap.replace(/-(\d\d)-(\d\d)/, '年$1月$2日') + '時点');

// ヒーロー & タイル
const cs = S.cohort_survival; const founded = sum(years.map(y => cs[y].founded)), closed = sum(years.map(y => cs[y].closed));
$('hero').textContent = fmt.format(founded);
$('t-closed').textContent = fmt.format(closed); $('t-closed-sub').textContent = pct(closed / founded) + ' が登記閉鎖';
$('t-listed').textContent = fmt.format(S.listed.total);
$('t-merged').textContent = fmt.format(S.merger.total);
$('t-univ').textContent = fmt.format(S.univ.in_scope);
for (const [id, group, label] of [['l-listed', 'exit', '上場している'], ['l-merged', 'exit', '合併で消滅した'], ['l-univ', 'attr', '大学発ベンチャー'], ['l-liq', 'exit', '清算して閉鎖した']]) { const u = catId(group, label); if (u && $(id)) $(id).href = u; }

// A. 年別 設立数 (法人種別)
const fk = S.founded_by_year_kind; const kinds = ['株式会社', '合同会社'];
const other = years.map(y => sum(Object.entries(fk[y]).filter(([k]) => !kinds.includes(k)).map(([, v]) => v)));
stackedColumns($('c-founded'), { categories: years.map(y => y === partial ? y + '*' : y), series: [
  { name: '株式会社', color: C.s1, values: years.map(y => fk[y]['株式会社'] || 0) },
  { name: '合同会社', color: C.s2, values: years.map(y => fk[y]['合同会社'] || 0) },
  { name: 'その他の法人', color: C.s3, values: other }], unit: '件' });

// B. コホート別 閉鎖 (事由別)
const reasons = ['清算の結了等', '合併による解散等', '登記官による閉鎖'];
stackedColumns($('c-cohort'), { categories: years, series: reasons.map((r, i) => ({ name: r, color: [C.muted, C.s2, C.s8][i], values: years.map(y => cs[y].by_reason[r] || 0) })), unit: '社',
  note: years.map(y => `　閉鎖率 ${pct(cs[y].closed / cs[y].founded)}`) });
const rateRows = years.map(y => [y, cs[y].founded, cs[y].closed, pct(cs[y].closed / cs[y].founded)]);
$('cohort-note').textContent = `設立年別の閉鎖率: ` + rateRows.filter(r => +r[0] <= 2020).map(r => `${r[0]}年 ${r[3]}`).join(' / ');

// C. 生存曲線 (2016〜2023 コホート、序数ランプ)
const cohorts = Object.keys(S.survival_curve).filter(y => +y <= 2023).sort();
const months = Array.from(new Set(cohorts.flatMap(y => S.survival_curve[y].map(p => p[0])))).sort((a, b) => a - b);
lines($('c-survival'), { x: months, xFmt: m => m + 'か月', yFmt: v => (v * 100).toFixed(0) + '%', yMin: 0.85, yMax: 1,
  series: cohorts.map((y, i) => { const m = new Map(S.survival_curve[y].map(p => [p[0], p[1]])); return { name: y + '年設立', color: SEQ[i], values: months.map(mm => m.has(mm) ? m.get(mm) : null) }; }),
  endLabels: [] });

// D. 閉鎖の発生年
const cy = Object.keys(S.closures_by_year).filter(y => y >= '2016').sort();
stackedColumns($('c-closures'), { categories: cy.map(y => y === partial ? y + '*' : y), series: reasons.map((r, i) => ({ name: r, color: [C.muted, C.s2, C.s8][i], values: cy.map(y => S.closures_by_year[y][r] || 0) })), unit: '社' });

// E. 都道府県
const pref = S.pref_totals.slice(0, 15);
hBars($('c-pref'), { items: pref.map(p => ({ label: p.pref, value: p.founded, sub: pct(p.closed / p.founded) })), color: C.s1, unit: '設立数', subLabel: '閉鎖率' });
const tokyo = S.pref_totals.find(p => p.pref === '東京都'); if (tokyo) $('pref-note').textContent = `東京都が ${pct(tokyo.founded / sum(S.pref_totals.map(p => p.founded)))} を占めます。`;

// F. 上場
const ind = Object.entries(S.listed.by_industry).slice(0, 12);
hBars($('c-listed-ind'), { items: ind.map(([k, v]) => ({ label: k, value: v })), color: C.s1, unit: '社' });
stackedColumns($('c-listed-year'), { categories: years, series: [{ name: '上場している会社', color: C.s1, values: years.map(y => S.listed.by_cohort[y] || 0) }], unit: '社' });

// G. 合併の承継先
hBars($('c-succ'), { items: S.merger.top_successors.slice(0, 15).map(s => ({ label: s.name, value: s.n })), color: C.s2, unit: '吸収した会社数' });

// H. 商号キーワード
const kw = S.keyword_tags; $('kw-note').textContent = `2016年以降に設立された株式会社・合同会社 ${fmt.format(kw.population)} 社のうち、商号に業種を示す語が含まれるのは ${fmt.format(kw.tagged_any)} 社（${pct(kw.tagged_any / kw.population)}）だけです。それ以外は名称からは業種が分かりません。`;
hBars($('c-kw'), { items: kw.counts.map(k => ({ label: k.label, value: k.n })), color: C.muted, unit: '社' });

// I. 大学発
hBars($('c-univ'), { items: S.univ.by_university.map(u => ({ label: u.university, value: u.n })), color: C.s3, unit: '社' });
hBars($('c-univ-field'), { items: S.univ.by_field.slice(0, 12).map(u => ({ label: u.field, value: u.n })), color: C.s3, unit: '社' });
$('univ-note').textContent = `データベースには ${fmt.format(S.univ.total_in_db)} 社が掲載され、そのうち2016年以降に設立された会社は ${fmt.format(S.univ.in_scope)} 社です。`;
