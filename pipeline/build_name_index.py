"""全法人（583万件）の名称の出現回数を name_count テーブルに入れる。
名寄せで「同名法人が全国に1社しかない」ことを確認するために使う（2016年以降の会社だけで一意でも、古い同名会社がありうる）。
usage: python build_name_index.py <zenkoku_all.csv> <db_path>
"""
import sys, csv, sqlite3, unicodedata, re, collections
csv_path, db = sys.argv[1], sys.argv[2]
CORP = re.compile(r'(株式会社|合同会社|有限会社|合資会社|合名会社)')
norm = lambda s: CORP.sub('', unicodedata.normalize('NFKC', s)).replace(' ', '').replace('　', '').lower()
cnt = collections.Counter(); alive = collections.Counter()
with open(csv_path, encoding='utf-8', newline='') as fh:
    for r in csv.reader(fh):
        if r[8] not in ('301', '302', '303', '304', '305'): continue
        k = norm(r[6]); cnt[k] += 1
        if not r[18]: alive[k] += 1
con = sqlite3.connect(db)
con.executescript("DROP TABLE IF EXISTS name_count; CREATE TABLE name_count (norm_name TEXT PRIMARY KEY, n INTEGER NOT NULL, n_alive INTEGER NOT NULL);")
con.executemany("INSERT INTO name_count VALUES (?,?,?)", [(k, v, alive.get(k, 0)) for k, v in cnt.items()])
con.commit(); print(f"名称 {len(cnt)} 種 / 会社 {sum(cnt.values())} 社")
