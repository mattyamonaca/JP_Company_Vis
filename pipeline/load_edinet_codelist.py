"""EDINETコードリスト (Edinetcode.zip) → snapshot_edinet_filer / company_tag(tier1 industry_jpx33) / company_scope.is_listed
usage: python load_edinet_codelist.py <Edinetcode.zip> <db_path> <snapshot_date>
"""
import sys, zipfile, io, csv, sqlite3, datetime
zip_path, db_path, snapshot = sys.argv[1], sys.argv[2], sys.argv[3]
with zipfile.ZipFile(zip_path) as z:
    name = [n for n in z.namelist() if n.lower().endswith('.csv')][0]
    rows = list(csv.reader(io.TextIOWrapper(io.BytesIO(z.read(name)), encoding='cp932', errors='ignore')))
hdr = rows[1]; data = rows[2:]
ix = {h: i for i, h in enumerate(hdr)}
con = sqlite3.connect(db_path)
recs = []
for r in data:
    hb = r[ix['提出者法人番号']].strip()
    recs.append((snapshot, r[ix['ＥＤＩＮＥＴコード']], hb or None, r[ix['提出者名']], r[ix['提出者種別']],
                 r[ix['上場区分']], r[ix['提出者業種']], r[ix['証券コード']].strip() or None,
                 int(r[ix['資本金']] or 0) if r[ix['資本金']].strip().isdigit() else None, r[ix['決算日']]))
con.executemany("INSERT OR REPLACE INTO snapshot_edinet_filer VALUES (?,?,?,?,?,?,?,?,?,?)", recs)
# tier1 業種タグ (33業種) は上場企業のみ。company に存在する法人番号だけ付与
con.execute("""INSERT OR REPLACE INTO company_tag(houjin_bangou,tag_type,tag_value,tag_label,tier,confidence,source_id,evidence_ref)
  SELECT s.houjin_bangou,'industry_jpx33',s.industry_jpx33,s.industry_jpx33,1,1.0,'edinet',s.edinet_code
  FROM snapshot_edinet_filer s JOIN company c ON c.houjin_bangou=s.houjin_bangou
  WHERE s.snapshot_date=? AND s.listing_status='上場' AND s.industry_jpx33<>''""", (snapshot,))
con.execute("""UPDATE company_scope SET is_listed=1 WHERE houjin_bangou IN (
  SELECT houjin_bangou FROM snapshot_edinet_filer WHERE snapshot_date=? AND listing_status='上場' AND houjin_bangou IS NOT NULL)""", (snapshot,))
con.execute("INSERT OR REPLACE INTO source VALUES (?,?,?,?,?,?,?)", (
  'edinet','金融庁','EDINET（EDINETコードリスト・開示書類）','https://disclosure2.edinet-fsa.go.jp/',
  'PDL1.0（CC BY 4.0互換）','EDINET閲覧（提出）サイト（金融庁）（https://disclosure2.edinet-fsa.go.jp/）を加工して作成',
  'スクレイピング禁止。API・コードリストの正規ダウンロードのみ'))
con.execute("INSERT INTO ingest_run(source_id,snapshot_date,retrieved_at,file_name,row_count) VALUES (?,?,?,?,?)",
  ('edinet', snapshot, datetime.datetime.now().isoformat(timespec='seconds'), zip_path.split('/')[-1], len(recs)))
con.commit()
n_listed = con.execute("SELECT COUNT(*) FROM company_scope WHERE is_listed=1").fetchone()[0]
n_tag = con.execute("SELECT COUNT(*) FROM company_tag WHERE tag_type='industry_jpx33'").fetchone()[0]
print(f"コードリスト {len(recs)} 行 / 2016年以降設立で上場 {n_listed} 社 / 業種タグ {n_tag} 件")
