"""data/edinet_docs.jsonl → raw_edinet_document / company_scope の出口フラグ
- has_ipo_filing / ipo_year : 有価証券届出書(新規公開時) を提出した会社
- is_tob_target / tob_year  : 公開買付届出書の対象会社になった会社 (subjectEdinetCode → 法人番号)
- filed_annual_report       : 有価証券報告書を提出したことがある会社
法人番号は書類の JCN → なければ EDINETコードリスト(snapshot_edinet_filer) で補完。
usage: python load_edinet_docs.py <db_path>
"""
import sys, json, sqlite3, collections
db = sys.argv[1]; con = sqlite3.connect(db)
for col in ('has_ipo_filing INTEGER', 'ipo_year INTEGER', 'is_tob_target INTEGER', 'tob_year INTEGER', 'filed_annual_report INTEGER'):
    try: con.execute(f"ALTER TABLE company_scope ADD COLUMN {col}")
    except sqlite3.OperationalError: pass
ec2hb = {}
for ec, hb in con.execute("SELECT edinet_code, houjin_bangou FROM snapshot_edinet_filer WHERE houjin_bangou IS NOT NULL"): ec2hb[ec] = hb
try: con.execute("ALTER TABLE raw_edinet_document ADD COLUMN sec_code TEXT")
except sqlite3.OperationalError: pass
con.execute("DELETE FROM raw_edinet_document"); rows = []; n = 0
with open('data/edinet_docs.jsonl', encoding='utf-8') as fh:
    for line in fh:
        d = json.loads(line); n += 1
        hb = (d.get('JCN') or '').strip() or ec2hb.get(d.get('edinetCode') or '')
        if d.get('JCN') and d.get('edinetCode') and d['edinetCode'] not in ec2hb: ec2hb[d['edinetCode']] = d['JCN'].strip()
        ipo = 1 if d.get('docTypeCode') == '030' and '新規公開' in (d.get('docDescription') or '') else 0
        rows.append((d['docID'], d.get('edinetCode'), hb, d.get('filerName'), d.get('docTypeCode'), d.get('formCode'), d.get('submitDateTime'),
                     d.get('periodStart'), d.get('periodEnd'), d.get('subjectEdinetCode'), d.get('docDescription'), ipo, None, (d.get('secCode') or '').strip() or None))
con.executemany("INSERT OR REPLACE INTO raw_edinet_document VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
# フラグ初期化
con.execute("UPDATE company_scope SET has_ipo_filing=0, ipo_year=NULL, is_tob_target=0, tob_year=NULL, filed_annual_report=0")
# 上場した: (a) 有価証券届出書(新規公開時) がある [EDINETの縦覧期間の都合で2021年9月以降のみ]
#           (b) 証券コード付きで有価証券報告書を提出したことがある [有報は10年分。未上場の有報提出者は証券コードなし]
ipo = {}
for hb, dt in con.execute("SELECT houjin_bangou, MIN(submit_datetime) FROM raw_edinet_document WHERE is_ipo_filing=1 AND houjin_bangou IS NOT NULL GROUP BY 1"): ipo[hb] = int(dt[:4])
for hb, dt in con.execute("SELECT houjin_bangou, MIN(submit_datetime) FROM raw_edinet_document WHERE doc_type_code='120' AND houjin_bangou IS NOT NULL AND sec_code IS NOT NULL AND sec_code<>'' GROUP BY 1"):
    y = int(dt[:4]); ipo[hb] = min(ipo.get(hb, y), y)
con.executemany("UPDATE company_scope SET has_ipo_filing=1, ipo_year=? WHERE houjin_bangou=?", [(y, hb) for hb, y in ipo.items()])
# TOB対象: subjectEdinetCode → 法人番号
tob = {}
for sec, dt in con.execute("SELECT subject_edinet_code, MIN(submit_datetime) FROM raw_edinet_document WHERE doc_type_code='240' AND subject_edinet_code IS NOT NULL GROUP BY 1"):
    hb = ec2hb.get(sec)
    if hb: tob[hb] = int(dt[:4])
con.executemany("UPDATE company_scope SET is_tob_target=1, tob_year=? WHERE houjin_bangou=?", [(y, hb) for hb, y in tob.items()])
con.execute("UPDATE company_scope SET filed_annual_report=1 WHERE houjin_bangou IN (SELECT DISTINCT houjin_bangou FROM raw_edinet_document WHERE doc_type_code='120' AND houjin_bangou IS NOT NULL)")
con.commit()
q = lambda s: con.execute(s).fetchone()[0]
print(f"書類 {n} 件 / 上場した(全体) {len(ipo)} 社, うち2016年以降設立の会社 {q('SELECT COUNT(*) FROM company_scope WHERE has_ipo_filing=1 AND founded_2016plus=1 AND is_company=1')} 社")
print(f"TOB対象(全体) {len(tob)} 社, うち2016年以降設立 {q('SELECT COUNT(*) FROM company_scope WHERE is_tob_target=1 AND founded_2016plus=1 AND is_company=1')} 社")
print(f"有報提出あり 2016年以降設立 {q('SELECT COUNT(*) FROM company_scope WHERE filed_annual_report=1 AND founded_2016plus=1 AND is_company=1')} 社 / 現在上場 {q('SELECT COUNT(*) FROM company_scope WHERE is_listed=1 AND founded_2016plus=1 AND is_company=1')} 社")
print("IPO届出ありで現在非上場(2016年以降設立):", q("SELECT COUNT(*) FROM company_scope WHERE has_ipo_filing=1 AND founded_2016plus=1 AND is_company=1 AND COALESCE(is_listed,0)=0"))
