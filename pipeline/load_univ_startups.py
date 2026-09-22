"""経産省 大学発ベンチャーデータベース (Excel) → raw_meti_univ_startup / company_tag(tier2 field) / company_scope.is_univ_startup
個人情報 (代表者氏名・電話・メール・研究者名) は取り込まない。
usage: python load_univ_startups.py <Univ-venture_db_data.xlsx> <db_path> <snapshot_date>
"""
import sys, sqlite3, datetime, openpyxl, unicodedata
xlsx, db_path, snapshot = sys.argv[1], sys.argv[2], sys.argv[3]
con = sqlite3.connect(db_path)
for col in ('stage TEXT', 'ipo_market TEXT', 'employee_number INTEGER'):
    try: con.execute(f"ALTER TABLE raw_meti_univ_startup ADD COLUMN {col}")
    except sqlite3.OperationalError: pass
wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True); ws = wb['統合DB']
it = ws.iter_rows(values_only=True); hdr = next(it); ix = {h: i for i, h in enumerate(hdr) if h}
def g(r, k):
    v = r[ix[k]] if k in ix else None
    return None if v in (None, '') else str(v).strip()
recs = []
for i, r in enumerate(it):
    name = g(r, '企業名')
    if not name: continue
    hb = g(r, '法人番号'); hb = hb if hb and hb.isdigit() and len(hb) == 13 else None
    fy = g(r, '設立年'); fy = int(float(fy)) if fy and fy.replace('.', '').isdigit() else None
    emp = g(r, '正社員数_現在'); emp = int(float(emp)) if emp and emp.replace('.', '').isdigit() else None
    recs.append((f"univ-{i+2}", name, g(r, '関連大学'), g(r, '主力製品サービス関連技術分野'), fy, g(r, '都道府県名'),
                 2025, hb, None, g(r, '事業ステージ'), g(r, '株式公開 上場市場名'), emp))
con.executemany("""INSERT OR REPLACE INTO raw_meti_univ_startup
  (record_id,company_name,university,field,founded_year,pref,survey_year,houjin_bangou,run_id,stage,ipo_market,employee_number)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", recs)
# 法人番号がない行は商号の完全一致で名寄せ (同名が1社のときだけ)
norm = lambda s: unicodedata.normalize('NFKC', s).replace(' ', '').replace('　', '').lower()
unresolved = con.execute("SELECT record_id, company_name FROM raw_meti_univ_startup WHERE houjin_bangou IS NULL").fetchall()
if unresolved:
    names = {}
    for hb, nm in con.execute("SELECT houjin_bangou, name FROM company"):
        names.setdefault(norm(nm), []).append(hb)
    for rid, nm in unresolved:
        c = names.get(norm(nm), [])
        con.execute("INSERT OR REPLACE INTO name_match VALUES (?,?,?,?,?,?,?,?)",
                    ('meti_univ', rid, nm, norm(nm), c[0] if len(c) == 1 else None, 'exact', len(c), 1 if len(c) > 1 else 0))
        if len(c) == 1: con.execute("UPDATE raw_meti_univ_startup SET houjin_bangou=? WHERE record_id=?", (c[0], rid))
con.execute("""INSERT OR REPLACE INTO company_tag(houjin_bangou,tag_type,tag_value,tag_label,tier,confidence,source_id,evidence_ref)
  SELECT u.houjin_bangou,'field',u.field,u.field,2,0.9,'meti_univ',u.record_id
  FROM raw_meti_univ_startup u JOIN company c ON c.houjin_bangou=u.houjin_bangou WHERE u.field IS NOT NULL""")
con.execute("""UPDATE company_scope SET is_univ_startup=1 WHERE houjin_bangou IN
  (SELECT houjin_bangou FROM raw_meti_univ_startup WHERE houjin_bangou IS NOT NULL)""")
con.execute("INSERT OR REPLACE INTO source VALUES (?,?,?,?,?,?,?)", (
  'meti_univ','経済産業省','大学発ベンチャーデータベース','https://www.meti.go.jp/policy/innovation_corp/univ-startupsdb.html',
  'PDL1.0（CC BY 4.0互換）','大学発ベンチャーデータベース（経済産業省）を加工して作成','掲載許諾企業のみ収録。連絡先等の個人情報は取り込まない'))
con.execute("INSERT INTO ingest_run(source_id,snapshot_date,retrieved_at,file_name,row_count) VALUES (?,?,?,?,?)",
  ('meti_univ', snapshot, datetime.datetime.now().isoformat(timespec='seconds'), xlsx.split('/')[-1], len(recs)))
con.commit()
n_in = con.execute("SELECT COUNT(*) FROM company_scope WHERE is_univ_startup=1").fetchone()[0]
n_hb = con.execute("SELECT COUNT(*) FROM raw_meti_univ_startup WHERE houjin_bangou IS NOT NULL").fetchone()[0]
print(f"大学発ベンチャー {len(recs)} 社 / 法人番号あり {n_hb} / 2016年以降設立の会社に該当 {n_in}")
