"""SQLite → site/data/*.json  (完全静的サイト用の集計・カテゴリ別一覧)
usage: python build_site_data.py <db_path> <site/data dir>
"""
import sys, sqlite3, json, os, datetime, collections, shutil, hashlib
slug = lambda t: hashlib.md5(t.encode('utf-8')).hexdigest()[:8]
db_path, out = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db_path); con.row_factory = sqlite3.Row
PREF = {f"{i:02d}": n for i, n in enumerate(
 "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split(), 1)}
KIND = {'301':'株式会社','302':'有限会社','303':'合名会社','304':'合資会社','305':'合同会社','399':'その他の設立登記法人','401':'外国会社等','499':'その他','101':'国の機関','201':'地方公共団体'}
REASON = {'01':'清算の結了等','11':'合併による解散等','21':'登記官による閉鎖','31':'その他の清算の結了等'}
COMPANY = ('301','302','303','304','305')
YEARS = [str(y) for y in range(2016, 2027)]
snapshot = con.execute("SELECT snapshot_date FROM ingest_run WHERE source_id='nta_houjin' ORDER BY run_id DESC LIMIT 1").fetchone()[0]
def q(sql, *a): return [dict(r) for r in con.execute(sql, a)]
def write(path, obj):
    p = os.path.join(out, path); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    return os.path.getsize(p)
# 生成物だけ消す (cube.json は build_cube.py が作るので残す)
for sub in ('categories',):
    if os.path.isdir(os.path.join(out, sub)): shutil.rmtree(os.path.join(out, sub))
os.makedirs(out, exist_ok=True)

S = {'snapshot_date': snapshot, 'years': YEARS}
# 1. 設立数 (指定年×法人種別, 全法人)
agg = q("SELECT assign_year, kind_code, close_reason_code, n FROM agg_year_kind")
fy = collections.defaultdict(lambda: collections.Counter())
for r in agg:
    if r['assign_year'] in YEARS: fy[r['assign_year']][KIND.get(r['kind_code'], 'その他')] += r['n']
S['founded_by_year_kind'] = {y: dict(fy[y]) for y in YEARS}
S['bulk_assigned_total'] = sum(r['n'] for r in agg if r['assign_year'] == 'bulk')
# 2. コホート別 生存状況 (会社)
cs = {}
for y in YEARS:
    rows = [r for r in agg if r['assign_year'] == y and r['kind_code'] in COMPANY]
    founded = sum(r['n'] for r in rows); closed = sum(r['n'] for r in rows if r['close_reason_code'])
    cs[y] = {'founded': founded, 'closed': closed,
             'by_reason': {REASON.get(k, k): sum(r['n'] for r in rows if r['close_reason_code'] == k) for k in REASON}}
S['cohort_survival'] = cs
# 3. 生存曲線 (株式会社+合同会社, 経過月数ごとの生存率, スナップショット日で打ち切り)
snap = datetime.date.fromisoformat(snapshot)
def months(a, b): return (b.year - a.year) * 12 + (b.month - a.month)
curve = {}
for y in YEARS[:-1]:
    rows = con.execute("SELECT assigned_on, closed_on FROM company WHERE kind_code IN ('301','305') AND substr(assigned_on,1,4)=?", (y,)).fetchall()
    # 各社の「観測できた月数」と「閉鎖までの月数」を先に計算
    obs = []
    for a, c in rows:
        ad = datetime.date.fromisoformat(a)
        obs.append((months(ad, snap), months(ad, datetime.date.fromisoformat(c)) if c else None))
    pts = []
    for m in range(0, 121, 6):
        at_risk = sum(1 for o, _ in obs if o >= m)
        if at_risk < 1000: break
        alive = sum(1 for o, cm in obs if o >= m and (cm is None or cm > m))
        pts.append([m, round(alive / at_risk, 4), at_risk])
    curve[y] = pts
S['survival_curve'] = curve
# 4. 閉鎖の発生年×事由 (2016年以降設立の会社)
cb = collections.defaultdict(lambda: collections.Counter())
for r in q("SELECT substr(closed_on,1,4) y, close_reason_code rc, COUNT(*) n FROM company WHERE closed_on IS NOT NULL AND assigned_on>='2016-01-01' AND kind_code IN ('301','302','303','304','305') GROUP BY 1,2"):
    cb[r['y']][REASON.get(r['rc'], r['rc'])] = r['n']
S['closures_by_year'] = {y: dict(v) for y, v in sorted(cb.items())}
# 5. 都道府県 (会社, 2016年以降)
pt = collections.defaultdict(lambda: {'founded': 0, 'closed': 0}); pby = collections.defaultdict(lambda: collections.Counter())
for r in q("SELECT assign_year, pref_code, SUM(n) n, SUM(closed) c FROM agg_year_pref WHERE assign_year>='2016' GROUP BY 1,2"):
    name = PREF.get(r['pref_code'], '不明'); pt[name]['founded'] += r['n']; pt[name]['closed'] += r['c']; pby[r['assign_year']][name] += r['n']
S['pref_totals'] = sorted([{'pref': k, **v} for k, v in pt.items()], key=lambda x: -x['founded'])
S['pref_by_year'] = {y: dict(pby[y]) for y in YEARS}
# 6. 上場 (2016年以降設立で現在上場)
S['listed'] = {
  'total': con.execute("SELECT COUNT(*) FROM company_scope WHERE is_listed=1 AND founded_2016plus=1 AND is_company=1").fetchone()[0],
  'by_cohort': {r['y']: r['n'] for r in q("SELECT cohort_year y, COUNT(*) n FROM company_scope WHERE is_listed=1 AND founded_2016plus=1 AND is_company=1 GROUP BY 1")},
  'by_industry': {r['v']: r['n'] for r in q("SELECT t.tag_label v, COUNT(*) n FROM company_tag t JOIN company_scope s USING(houjin_bangou) WHERE t.tag_type='industry_jpx33' AND s.founded_2016plus=1 AND s.is_company=1 GROUP BY 1 ORDER BY 2 DESC")}}
# 7. 合併: 承継先ランキング
S['merger'] = {
  'total': con.execute("SELECT COUNT(*) FROM company WHERE close_reason_code='11' AND assigned_on>='2016-01-01'").fetchone()[0],
  'top_successors': q("""SELECT s.houjin_bangou hb, s.name, COUNT(*) n FROM company c JOIN company s ON s.houjin_bangou=c.successor_houjin_bangou
     WHERE c.close_reason_code='11' AND c.assigned_on>='2016-01-01' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20""")}
# 8. 商号キーワードタグ
kw = q("SELECT tag_value code, tag_label label, COUNT(*) n FROM company_tag WHERE tag_type='keyword' GROUP BY 1,2 ORDER BY 3 DESC")
kwc = collections.defaultdict(lambda: collections.Counter())
for r in q("SELECT t.tag_label l, substr(c.assigned_on,1,4) y, COUNT(*) n FROM company_tag t JOIN company c USING(houjin_bangou) WHERE t.tag_type='keyword' GROUP BY 1,2"):
    kwc[r['l']][r['y']] = r['n']
tot2016 = con.execute("SELECT COUNT(*) FROM company WHERE assigned_on>='2016-01-01' AND kind_code IN ('301','305')").fetchone()[0]
S['keyword_tags'] = {'population': tot2016, 'tagged_any': con.execute("SELECT COUNT(DISTINCT houjin_bangou) FROM company_tag WHERE tag_type='keyword'").fetchone()[0],
                     'counts': kw, 'by_year': {k: dict(v) for k, v in kwc.items()}}
# 9. 大学発ベンチャー
S['univ'] = {
  'total_in_db': con.execute("SELECT COUNT(*) FROM raw_meti_univ_startup").fetchone()[0],
  'in_scope': con.execute("SELECT COUNT(*) FROM company_scope WHERE is_univ_startup=1 AND founded_2016plus=1 AND is_company=1").fetchone()[0],
  'by_university': q("SELECT university, COUNT(*) n FROM raw_meti_univ_startup u JOIN company c USING(houjin_bangou) WHERE university IS NOT NULL AND c.assigned_on>='2016-01-01' AND c.kind_code IN ('301','302','303','304','305') GROUP BY 1 ORDER BY 2 DESC LIMIT 15"),
  'by_field': q("SELECT field, COUNT(*) n FROM raw_meti_univ_startup u JOIN company c USING(houjin_bangou) WHERE field IS NOT NULL AND c.assigned_on>='2016-01-01' AND c.kind_code IN ('301','302','303','304','305') GROUP BY 1 ORDER BY 2 DESC"),
  'by_cohort': {r['y']: r['n'] for r in q("SELECT cohort_year y, COUNT(*) n FROM company_scope WHERE is_univ_startup=1 AND founded_2016plus=1 AND is_company=1 GROUP BY 1")}}
print("summary.json", write('summary.json', S), "bytes")

# ---------- カテゴリ別一覧 ----------
PAGE = 500
def status(r):
    if not r['closed_on']: return 'A'
    return {'01': 'L', '11': 'M', '21': 'R'}.get(r['close_reason_code'], 'O')
BASE = """SELECT c.houjin_bangou hb, c.name, c.pref_code, substr(c.assigned_on,1,4) y, c.closed_on, c.close_reason_code,
          s.name succ FROM company c LEFT JOIN company s ON s.houjin_bangou=c.successor_houjin_bangou"""
cats = []
def emit(cat_id, group, label, sql, params=(), desc='', tier=None, extra=None):
    rows = con.execute(sql, params).fetchall()
    rows.sort(key=lambda r: (-int(r['y']), r['name']))
    out_rows = [[r['hb'], r['name'], PREF.get(r['pref_code'], ''), int(r['y']), status(r), (extra(r) if extra else (r['succ'] or ''))] for r in rows]
    pages = max(1, (len(out_rows) + PAGE - 1) // PAGE)
    for p in range(pages): write(f'categories/{cat_id}/{p+1}.json', out_rows[p*PAGE:(p+1)*PAGE])
    st = collections.Counter(r[4] for r in out_rows)
    cats.append({'id': cat_id, 'group': group, 'label': label, 'count': len(out_rows), 'pages': pages, 'tier': tier, 'description': desc, 'status': dict(st)})
W = " WHERE c.assigned_on>='2016-01-01' AND c.kind_code IN ('301','302','303','304','305')"
emit('listed', 'exit', '上場している', BASE + " JOIN company_scope sc ON sc.houjin_bangou=c.houjin_bangou" + W + " AND sc.is_listed=1",
     desc='EDINETコードリストで上場区分が「上場」の会社', tier=1,
     extra=lambda r: (con.execute("SELECT tag_label FROM company_tag WHERE houjin_bangou=? AND tag_type='industry_jpx33'", (r['hb'],)).fetchone() or [''])[0])
emit('merged', 'exit', '合併で消滅した', BASE + W + " AND c.close_reason_code='11'", desc='登記記録の閉鎖事由が「合併による解散等」。相手先は承継先法人番号から', tier=1)
emit('liquidated', 'exit', '清算して閉鎖した', BASE + W + " AND c.close_reason_code IN ('01','31')", desc='登記記録の閉鎖事由が「清算の結了等」', tier=1)
emit('ipo', 'exit', '上場した', BASE + " JOIN company_scope sc ON sc.houjin_bangou=c.houjin_bangou" + W + " AND sc.has_ipo_filing=1",
     desc='EDINETに新規公開時の有価証券届出書、または証券コード付きの有価証券報告書がある会社', tier=1,
     extra=lambda r: (lambda x: f"上場 {x[0]}年" + ("（現在は非上場）" if not x[1] else '') if x else '')(con.execute("SELECT ipo_year, is_listed FROM company_scope WHERE houjin_bangou=?", (r['hb'],)).fetchone()))
emit('tob', 'exit', 'TOB（公開買付）の対象になった', BASE + " JOIN company_scope sc ON sc.houjin_bangou=c.houjin_bangou" + W + " AND sc.is_tob_target=1",
     desc='EDINETの公開買付届出書で対象会社になった会社（届出書の縦覧期間の都合で直近5年分）', tier=1,
     extra=lambda r: (lambda x: f"TOB {x[0]}年" if x and x[0] else '')(con.execute("SELECT tob_year FROM company_scope WHERE houjin_bangou=?", (r['hb'],)).fetchone()))
emit('acquired', 'exit', '上場企業に買収された（株式取得）', BASE + " JOIN company_scope sc ON sc.houjin_bangou=c.houjin_bangou" + W + " AND sc.acquired_by_listed=1",
     desc='上場企業の有価証券報告書の企業結合注記・キャッシュフロー注記に被取得企業として記載', tier=1,
     extra=lambda r: (lambda x: (x[1] or '') + (f'（{x[0]}年）' if x and x[0] else '') if x else '')(con.execute("SELECT sc.acquired_year, s.name FROM company_scope sc LEFT JOIN company s ON s.houjin_bangou=sc.acquirer_houjin_bangou WHERE sc.houjin_bangou=?", (r['hb'],)).fetchone()))
emit('acquirer', 'exit', '他社を吸収した（合併の承継先）', BASE + W + " AND c.houjin_bangou IN (SELECT successor_houjin_bangou FROM company WHERE close_reason_code='11' AND successor_houjin_bangou IS NOT NULL)",
     desc='2016年以降設立の会社を吸収合併で承継した会社。グループ内再編を多く含む', tier=1,
     extra=lambda r: str(con.execute("SELECT COUNT(*) FROM company WHERE successor_houjin_bangou=? AND close_reason_code='11'", (r['hb'],)).fetchone()[0]) + ' 社を吸収')
emit('univ', 'attr', '大学発ベンチャー', BASE + " JOIN company_scope sc ON sc.houjin_bangou=c.houjin_bangou" + W + " AND sc.is_univ_startup=1",
     desc='経産省 大学発ベンチャーデータベース掲載企業', tier=1,
     extra=lambda r: (con.execute("SELECT university FROM raw_meti_univ_startup WHERE houjin_bangou=? LIMIT 1", (r['hb'],)).fetchone() or [''])[0] or '')
for r in q("SELECT DISTINCT tag_value v FROM company_tag WHERE tag_type='industry_jpx33'"):
    emit('jpx33-' + slug(r['v']), 'industry_jpx33', r['v'], BASE + " JOIN company_tag t ON t.houjin_bangou=c.houjin_bangou" + W + " AND t.tag_type='industry_jpx33' AND t.tag_value=?", (r['v'],), desc='上場企業の業種（EDINET 提出者業種）', tier=1)
for r in q("SELECT DISTINCT tag_value v FROM company_tag WHERE tag_type='field'"):
    emit('field-' + slug(r['v']), 'field', r['v'], BASE + " JOIN company_tag t ON t.houjin_bangou=c.houjin_bangou" + W + " AND t.tag_type='field' AND t.tag_value=?", (r['v'],), desc='大学発ベンチャーの主力製品・サービス関連技術分野', tier=2,
         extra=lambda r: (con.execute("SELECT university FROM raw_meti_univ_startup WHERE houjin_bangou=? LIMIT 1", (r['hb'],)).fetchone() or [''])[0] or '')
for r in q("SELECT DISTINCT tag_value v, tag_label l FROM company_tag WHERE tag_type='keyword'"):
    emit('kw-' + r['v'], 'keyword', r['l'], BASE + " JOIN company_tag t ON t.houjin_bangou=c.houjin_bangou" + W + " AND t.tag_type='keyword' AND t.tag_value=?", (r['v'],), desc='商号に含まれる語からの推定（精度は低い）', tier=3)
write('categories/index.json', cats)
write('meta.json', {'generated_at': datetime.datetime.now().isoformat(timespec='seconds'), 'snapshot_date': snapshot,
                    'sources': q("SELECT * FROM source"), 'runs': q("SELECT source_id, snapshot_date, retrieved_at, row_count FROM ingest_run"),
                    'status_codes': {'A': '存続', 'L': '清算結了', 'M': '合併消滅', 'R': '登記官閉鎖', 'O': 'その他閉鎖'}})
total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(out) for f in fs)
nfiles = sum(len(fs) for _, _, fs in os.walk(out))
print(f"カテゴリ {len(cats)} 件 / ファイル {nfiles} / 合計 {total/1e6:.1f} MB")
