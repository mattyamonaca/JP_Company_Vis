"""data/cc_mna.jsonl（Common Crawl由来のM&A見出し）→ raw_web_acquisition / company_scope.acquired_web
対象を 2016年以降設立の会社に名寄せ（法人格を外した名称の完全一致、同名が1社のときだけ）。
usage: python load_cc_mna.py <db_path>
"""
import sys, json, sqlite3, re, unicodedata, collections
db = sys.argv[1]; con = sqlite3.connect(db)
con.executescript("""
CREATE TABLE IF NOT EXISTS raw_web_acquisition (
  url TEXT NOT NULL, source TEXT, published TEXT, title TEXT, buyer_name TEXT, buyer_code TEXT, target_raw TEXT, target_houjin_bangou TEXT, kind TEXT, captured TEXT,
  PRIMARY KEY (url, target_raw));
""")
for col in ('acquired_web INTEGER', 'acquired_web_year INTEGER', 'acquired_web_buyer TEXT', 'acquired_web_url TEXT', 'acquired_web_kind TEXT'):
    try: con.execute(f"ALTER TABLE company_scope ADD COLUMN {col}")
    except sqlite3.OperationalError: pass
CORP = re.compile(r'(株式会社|合同会社|有限会社|合資会社|合名会社|\(株\)|（株）|㈱)')
def norm(s): return CORP.sub('', unicodedata.normalize('NFKC', s)).replace(' ', '').replace('　', '').lower()
uniq = {k for (k,) in con.execute("SELECT norm_name FROM name_count WHERE n=1")}
names = collections.defaultdict(set); founded = {}
for hb, nm, a0 in con.execute("SELECT c.houjin_bangou, c.name, c.assigned_on FROM company c JOIN company_scope s USING(houjin_bangou) WHERE s.founded_2016plus=1 AND s.is_company=1"):
    names[norm(nm)].add(hb); founded[hb] = a0
ACQ = ('完全子会社化', '孫会社化', '子会社化', '株式を取得', '株式の一部を取得', '株式を追加取得', '株式取得', '買収', '関連会社化', '持分法適用関連会社化', '吸収合併')
DESC = re.compile(r'(メーカー|会社|事業者|運営|展開|手がける|手掛ける|提供|販売|開発|製造|企業|サービス|ベンチャー|スタートアップ|など|等)の')
def candidates(t):
    t = re.sub(r'(など|等)\d*社$', '', t.strip())
    out = [t]
    if 'の' in t:
        out.append(t.rsplit('の', 1)[1]); m = DESC.search(t)
        if m: out.append(t[m.end():])
    # 「A・B」「AとB」の複数対象
    for sep in ('・', 'と', '、'):
        if sep in t: out += [x for x in t.split(sep) if 1 < len(x) < 30]
    return [c.strip('「」 ') for c in out if len(c.strip('「」 ')) >= 2]
rows = []; n = 0; matched = 0
for line in open('data/cc_mna.jsonl', encoding='utf-8'):
    d = json.loads(line); n += 1
    if not d.get('target') or d.get('kind') not in ACQ: continue
    hb = None; pub = d.get('published') or ''
    if pub < '2016': continue                       # 2016年以降設立の会社が対象なので、それ以前の記事は無関係
    for c in candidates(d['target']):
        s = names.get(norm(c))
        if s and len(s) == 1 and norm(c) in uniq:
            cand = next(iter(s))
            if founded.get(cand, '9999') <= pub: hb = cand; break   # 設立前の記事に一致する同名法人は別会社
    if hb: matched += 1
    buyer = re.sub(r'＜[^＞]*＞', '', d.get('buyer') or '').strip()
    rows.append((d['url'], d['source'], d.get('published'), d.get('title'), buyer, d.get('buyer_code'), d['target'], hb, d['kind'], d.get('captured')))
con.execute("DELETE FROM raw_web_acquisition"); con.executemany("INSERT OR REPLACE INTO raw_web_acquisition VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
con.execute("UPDATE company_scope SET acquired_web=0, acquired_web_year=NULL, acquired_web_buyer=NULL, acquired_web_url=NULL, acquired_web_kind=NULL")
con.execute("""UPDATE company_scope SET acquired_web=1,
  acquired_web_year=(SELECT CAST(substr(MIN(published),1,4) AS INTEGER) FROM raw_web_acquisition w WHERE w.target_houjin_bangou=company_scope.houjin_bangou),
  acquired_web_buyer=(SELECT buyer_name FROM raw_web_acquisition w WHERE w.target_houjin_bangou=company_scope.houjin_bangou ORDER BY published LIMIT 1),
  acquired_web_url=(SELECT url FROM raw_web_acquisition w WHERE w.target_houjin_bangou=company_scope.houjin_bangou ORDER BY published LIMIT 1),
  acquired_web_kind=(SELECT kind FROM raw_web_acquisition w WHERE w.target_houjin_bangou=company_scope.houjin_bangou ORDER BY published LIMIT 1)
  WHERE houjin_bangou IN (SELECT target_houjin_bangou FROM raw_web_acquisition WHERE target_houjin_bangou IS NOT NULL)""")
con.commit()
q = lambda s: con.execute(s).fetchone()[0]
print(f"見出し {n} / 買収系 {len(rows)} / 2016年以降設立の会社に名寄せ {matched} / フラグ付与 {q('SELECT COUNT(*) FROM company_scope WHERE acquired_web=1')} 社")
for r in con.execute("SELECT published, buyer_name, target_raw, kind FROM raw_web_acquisition WHERE target_houjin_bangou IS NOT NULL ORDER BY published DESC LIMIT 8"): print('  ', r)
