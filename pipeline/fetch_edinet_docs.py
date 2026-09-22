"""EDINET 書類一覧を日付ごとに取得し、出口の判定に使う書類だけを data/edinet_docs.jsonl に蓄積する。
対象: 030 有価証券届出書(新規公開時) / 240 公開買付届出書 / 250 公開買付撤回届出書 / 120 有価証券報告書 (上場歴の把握用、メタデータのみ)
日付ごとの取得済みマークを data/edinet_days/ に置くので中断・再開できる。
usage: python fetch_edinet_docs.py <start YYYY-MM-DD> <end YYYY-MM-DD>
"""
import sys, os, json, time, datetime
sys.path.insert(0, os.path.dirname(__file__)); from edinet_api import documents
start, end = datetime.date.fromisoformat(sys.argv[1]), datetime.date.fromisoformat(sys.argv[2])
os.makedirs("data/edinet_days", exist_ok=True)
KEEP = {"030", "240", "250", "120"}
FIELDS = ["docID", "edinetCode", "secCode", "JCN", "filerName", "docTypeCode", "formCode", "ordinanceCode", "docDescription",
          "submitDateTime", "periodStart", "periodEnd", "subjectEdinetCode", "subsidiaryEdinetCode", "issuerEdinetCode", "parentDocID", "withdrawalStatus"]
out = open("data/edinet_docs.jsonl", "a", encoding="utf-8")
d = start; n_days = 0; n_docs = 0; t0 = time.time()
while d <= end:
    mark = f"data/edinet_days/{d.isoformat()}"
    if not os.path.exists(mark):
        res = documents(d.isoformat())
        if res.get("metadata", {}).get("status") != "200":
            print("ERROR", d, res.get("metadata")); sys.exit(1)
        rows = [{k: x.get(k) for k in FIELDS} for x in res.get("results", []) if x.get("docTypeCode") in KEEP]
        for r in rows: out.write(json.dumps(r, ensure_ascii=False) + "\n")
        out.flush(); open(mark, "w").write(str(len(rows))); n_docs += len(rows); n_days += 1
        time.sleep(0.3)
        if n_days % 100 == 0: print(f"{d} まで {n_days} 日 / {n_docs} 件 / {time.time()-t0:.0f}s", flush=True)
    d += datetime.timedelta(days=1)
print(f"done: {n_days} 日取得, {n_docs} 件追加")
