// 全体の傾向 (絞り込み非連動): 全法人種別の設立数 / 生存曲線 / 合併承継先
import { stackedColumns, hBars, lines } from './charts.js';
const C = { s1: 'var(--s1)', s2: 'var(--s2)', s3: 'var(--s3)' };
const SEQ = ['var(--seq-250)', 'var(--seq-300)', 'var(--seq-350)', 'var(--seq-400)', 'var(--seq-450)', 'var(--seq-500)', 'var(--seq-550)', 'var(--seq-600)'];
const $ = id => document.getElementById(id);
const sum = a => a.reduce((x, y) => x + (y || 0), 0);
const S = await (await fetch('data/summary.json')).json();
const years = S.years, partial = years[years.length - 1];
document.querySelectorAll('.snap').forEach(e => e.textContent = S.snapshot_date.replace(/-(\d\d)-(\d\d)/, '年$1月$2日') + '時点');

const fk = S.founded_by_year_kind; const kinds = ['株式会社', '合同会社'];
const other = years.map(y => sum(Object.entries(fk[y]).filter(([k]) => !kinds.includes(k)).map(([, v]) => v)));
stackedColumns($('c-founded'), { categories: years.map(y => y === partial ? y + '*' : y), series: [
  { name: '株式会社', color: C.s1, values: years.map(y => fk[y]['株式会社'] || 0) },
  { name: '合同会社', color: C.s2, values: years.map(y => fk[y]['合同会社'] || 0) },
  { name: 'その他の法人', color: C.s3, values: other }], unit: '件' });

const cohorts = Object.keys(S.survival_curve).filter(y => +y <= 2023).sort();
const months = Array.from(new Set(cohorts.flatMap(y => S.survival_curve[y].map(p => p[0])))).sort((a, b) => a - b);
lines($('c-survival'), { x: months, xFmt: m => m + 'か月', yFmt: v => (v * 100).toFixed(0) + '%', yMin: 0.85, yMax: 1,
  series: cohorts.map((y, i) => { const m = new Map(S.survival_curve[y].map(p => [p[0], p[1]])); return { name: y + '年設立', color: SEQ[i], values: months.map(mm => m.has(mm) ? m.get(mm) : null) }; }) });

hBars($('c-succ'), { items: S.merger.top_successors.slice(0, 15).map(s => ({ label: s.name, value: s.n })), color: C.s2, unit: '吸収した会社数' });
