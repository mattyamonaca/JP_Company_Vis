"""data/edinet_blocks/*.json.gz の注記から「株式取得による子会社化」を抽出し、
raw_edinet_acquisition と company_scope.acquired_by_listed / acquired_year / acquirer_houjin_bangou を更新する。
根拠:
  A 企業結合等関係の注記: 「被取得企業の名称」「企業結合日」「取得原価/取得の対価」「取得した議決権比率」
  B キャッシュ・フロー注記: 「株式の取得により新たに○○を連結した」
usage: python parse_acquisitions.py <db_path>
"""
import sys, os, glob, gzip, json, re, sqlite3, unicodedata, collections
db = sys.argv[1]; con = sqlite3.connect(db)
con.executescript("""
CREATE TABLE IF NOT EXISTS raw_edinet_acquisition (
  doc_id TEXT NOT NULL, acquirer_edinet_code TEXT, acquirer_houjin_bangou TEXT, acquirer_name TEXT, submit_date TEXT,
  target_name TEXT NOT NULL, target_houjin_bangou TEXT, combination_date TEXT, ratio TEXT, price TEXT, basis TEXT NOT NULL, snippet TEXT,
  PRIMARY KEY (doc_id, target_name, basis));
""")
for col in ('acquired_by_listed INTEGER', 'acquired_year INTEGER', 'acquirer_houjin_bangou TEXT'):
    try: con.execute(f"ALTER TABLE company_scope ADD COLUMN {col}")
    except sqlite3.OperationalError: pass
norm = lambda s: unicodedata.normalize('NFKC', s).replace(' ', '').replace('　', '').lower()
CORP = r'(?:株式会社|合同会社|有限会社|合資会社|合名会社)'
NAME = rf'((?:{CORP}[^\s、。（）()「」,，]{{1,40}})|(?:[^\s、。（）()「」,，]{{1,40}}{CORP}))'
def clean(n):
    n = re.split(r'事業の内容|の株式|の全株式|を取得|を子会社|の発行済|以下|（以下', n)[0]
    return re.sub(r'[※＊*]\d*$', '', n.strip('　 ')).strip()
def find_targets_A(t):
    out = []
    # 「被取得企業の名称」の後に続く会社名 (表形式でもテキストでも)
    for m in re.finditer(r'被取得企業の名称[：:　\s]*' + NAME, t): out.append(clean(m.group(1)))
    for m in re.finditer(r'被取得企業[：:　\s]*' + NAME, t): out.append(clean(m.group(1)))
    return out
def field(t, label_pat, after=60):
    m = re.search(label_pat + r'[：:　\s]*([^\s　]{1,' + str(after) + '})', t); return m.group(1) if m else None
ec2hb = {ec: hb for ec, hb in con.execute("SELECT edinet_code, houjin_bangou FROM snapshot_edinet_filer WHERE houjin_bangou IS NOT NULL")}
names = collections.defaultdict(list)
for hb, nm in con.execute("SELECT houjin_bangou, name FROM company"): names[norm(nm)].append(hb)
rows = []; ndoc = 0
for f in glob.glob('data/edinet_blocks/*.json.gz'):
    p = json.load(gzip.open(f, 'rt', encoding='utf-8')); d = p['doc']; B = p.get('blocks', {}); ndoc += 1
    acq_hb = (d.get('JCN') or '').strip() or ec2hb.get(d.get('edinetCode'))
    base = (d['docID'], d.get('edinetCode'), acq_hb, d.get('filerName'), (d.get('submitDateTime') or '')[:10])
    for key in ('bc_consolidated', 'bc_single'):
        t = B.get(key) or ''
        if not t or '取得' not in t: continue
        # 「取得による企業結合」段落ごとに分割して被取得企業を拾う
        for seg in re.split(r'(?=（企業結合等関係）|（取得による企業結合）|取得による企業結合)', t):
            if '被取得企業' not in seg: continue
            if re.search(r'共通支配下|子会社株式の追加取得|事業分離|株式の譲渡|子会社株式の譲渡', seg[:200]) and '被取得企業の名称' not in seg[:400]: continue
            for tn in set(find_targets_A(seg)):
                date = field(seg, r'企業結合日') or field(seg, r'取得日'); ratio = field(seg, r'取得した議決権比率|取得後の議決権比率|議決権比率'); price = field(seg, r'取得原価|取得の対価|取得対価')
                rows.append(base + (tn, None, date, ratio, price, 'A:企業結合注記', seg[:300]))
    t = B.get('acquired_by_shares') or ''
    for m in re.finditer(r'株式の取得により新たに' + NAME + r'(?:及び' + NAME + r')?を連結', t):
        for tn in (m.group(1), m.group(2)):
            if tn: rows.append(base + (clean(tn), None, None, None, None, 'B:株式取得CF注記', m.group(0)[:200]))
# 名寄せ
out = []
for r in rows:
    tn = r[5]; c = names.get(norm(tn), [])
    hb = c[0] if len(c) == 1 else None
    out.append(r[:6] + (hb,) + r[7:])
con.execute("DELETE FROM raw_edinet_acquisition")
con.executemany("INSERT OR REPLACE INTO raw_edinet_acquisition VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", out)
con.execute("UPDATE company_scope SET acquired_by_listed=0, acquired_year=NULL, acquirer_houjin_bangou=NULL")
con.execute("""UPDATE company_scope SET acquired_by_listed=1,
   acquired_year=(SELECT CAST(substr(COALESCE(MIN(combination_date), MIN(submit_date)),1,4) AS INTEGER) FROM raw_edinet_acquisition a WHERE a.target_houjin_bangou=company_scope.houjin_bangou),
   acquirer_houjin_bangou=(SELECT acquirer_houjin_bangou FROM raw_edinet_acquisition a WHERE a.target_houjin_bangou=company_scope.houjin_bangou ORDER BY submit_date LIMIT 1)
   WHERE houjin_bangou IN (SELECT target_houjin_bangou FROM raw_edinet_acquisition WHERE target_houjin_bangou IS NOT NULL)""")
con.commit()
q = lambda s: con.execute(s).fetchone()[0]
print(f"書類 {ndoc} / 抽出行 {len(out)} / 名寄せ成功 {sum(1 for r in out if r[6])} / 2016年以降設立の会社に該当 {q('SELECT COUNT(*) FROM company_scope WHERE acquired_by_listed=1 AND founded_2016plus=1 AND is_company=1')} 社")
for r in con.execute("SELECT acquirer_name, target_name, combination_date, price, basis FROM raw_edinet_acquisition WHERE target_houjin_bangou IN (SELECT houjin_bangou FROM company_scope WHERE founded_2016plus=1) ORDER BY submit_date DESC LIMIT 8"): print('  ', r)
