"""国税庁 法人番号 全件CSV → SQLite
  - company        : 2016年以降に番号指定された会社(301-305) + その合併承継先
  - agg_year_kind  : 全583万件を流し読みして 指定年×法人種別×閉鎖事由 を集計 (全法人種別のサマリー用)
usage: python load_houjin.py <zenkoku_all.csv> <db_path> <snapshot_date>
"""
import csv, sqlite3, sys, datetime, collections, os
csv_path, db_path, snapshot = sys.argv[1], sys.argv[2], sys.argv[3]
COMPANY_KINDS = {'301','302','303','304','305'}
SCHEMA = os.path.join(os.path.dirname(__file__), 'schema.sql')

def rec(r):
    return (r[1], r[6], r[28], r[24], r[8], r[13], r[14], r[9], r[10], r[11], r[15], r[16],
            r[22], 1 if r[22]=='2015-10-05' else 0, r[5], r[4], r[2], r[21],
            r[18] or None, r[19] or None, r[20] or None, int(r[29] or 0), snapshot)

con = sqlite3.connect(db_path)
con.executescript(open(SCHEMA, encoding='utf-8').read())
con.executescript("""
CREATE TABLE IF NOT EXISTS agg_year_kind (
  assign_year TEXT NOT NULL, kind_code TEXT NOT NULL, close_reason_code TEXT NOT NULL,
  n INTEGER NOT NULL, PRIMARY KEY (assign_year, kind_code, close_reason_code));
CREATE TABLE IF NOT EXISTS agg_year_pref (
  assign_year TEXT NOT NULL, pref_code TEXT NOT NULL, kind_code TEXT NOT NULL,
  n INTEGER NOT NULL, closed INTEGER NOT NULL, PRIMARY KEY (assign_year, pref_code, kind_code));
""")
con.execute("PRAGMA journal_mode=OFF"); con.execute("PRAGMA synchronous=OFF")
INS = "INSERT OR REPLACE INTO company VALUES (" + ",".join("?"*23) + ")"

agg = collections.Counter(); aggp = collections.Counter(); aggp_closed = collections.Counter()
successors = set(); batch = []; n = 0; total = 0
with open(csv_path, encoding='utf-8', newline='') as fh:
    for r in csv.reader(fh):
        total += 1
        y = 'bulk' if r[22]=='2015-10-05' else r[22][:4]
        agg[(y, r[8], r[19] or '')] += 1
        if r[8] in COMPANY_KINDS and y != 'bulk':
            aggp[(y, r[13] or '99', r[8])] += 1
            if r[18]: aggp_closed[(y, r[13] or '99', r[8])] += 1
        if r[8] in COMPANY_KINDS and r[22] >= '2016-01-01':
            batch.append(rec(r)); n += 1
            if r[20]: successors.add(r[20])
            if len(batch) >= 50000: con.executemany(INS, batch); batch = []
con.executemany(INS, batch); con.commit()

have = {x[0] for x in con.execute("SELECT houjin_bangou FROM company")}
need = successors - have; m = 0
if need:
    batch = []
    with open(csv_path, encoding='utf-8', newline='') as fh:
        for r in csv.reader(fh):
            if r[1] in need: batch.append(rec(r)); m += 1
    con.executemany(INS, batch)

con.executemany("INSERT OR REPLACE INTO agg_year_kind VALUES (?,?,?,?)", [(k[0],k[1],k[2],v) for k,v in agg.items()])
con.executemany("INSERT OR REPLACE INTO agg_year_pref VALUES (?,?,?,?,?)", [(k[0],k[1],k[2],v,aggp_closed.get(k,0)) for k,v in aggp.items()])
con.execute("INSERT OR REPLACE INTO source VALUES (?,?,?,?,?,?,?)", (
  'nta_houjin','国税庁','法人番号公表サイト 全件データ','https://www.houjin-bangou.nta.go.jp/',
  'PDL1.0（CC BY 4.0互換）','国税庁法人番号公表サイト（国税庁）（https://www.houjin-bangou.nta.go.jp/）を加工して作成',
  'Web-API利用時は所定の免責文言を表示'))
con.execute("INSERT INTO ingest_run(source_id,snapshot_date,retrieved_at,file_name,row_count) VALUES (?,?,?,?,?)",
  ('nta_houjin', snapshot, datetime.datetime.now().isoformat(timespec='seconds'), os.path.basename(csv_path), total))
con.execute("""INSERT OR REPLACE INTO company_scope(houjin_bangou,cohort_year,is_company,founded_2016plus)
  SELECT houjin_bangou, CASE WHEN is_bulk_assigned=1 THEN NULL ELSE CAST(substr(assigned_on,1,4) AS INTEGER) END,
         kind_code IN ('301','302','303','304','305'), assigned_on>='2016-01-01' FROM company""")
con.commit()
print(f"全件 {total} 行を走査 / company に対象会社 {n} 件 + 承継先 {m} 件を投入 / agg_year_kind {len(agg)} 行")
