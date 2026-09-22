"""上場企業の有価証券報告書 (docTypeCode 120, 証券コードあり) から、株式取得の判定に使う注記だけを取り出して保存する。
EDINET API type=5 (XBRL→CSV, 約100KB/書類) を使い、必要なテキストブロックだけ data/edinet_blocks/<docID>.json.gz に残す。
新しい提出日から順に取得。取得済みはスキップするので中断・再開できる。
usage: python fetch_edinet_blocks.py [--since YYYY] [--limit N]
"""
import sys, os, json, gzip, zipfile, io, csv, time, argparse, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(__file__)); from edinet_api import api_key, API
ap = argparse.ArgumentParser(); ap.add_argument('--since', default='2017'); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--wait', type=float, default=0.25)
a = ap.parse_args()
BLOCKS = {
  'NotesBusinessCombinationsConsolidatedFinancialStatementsTextBlock': 'bc_consolidated',
  'NotesBusinessCombinationsFinancialStatementsTextBlock': 'bc_single',
  'MajorComponentsOfAssetsAndLiabilitiesOfConsolidatedSubsidiaryAcquiredByPurchaseOfSharesDuringReportingPeriodTextBlock': 'acquired_by_shares',
  'NumberOfConsolidatedSubsidiariesAndNamesOfMajorConsolidatedSubsidiariesTextBlock': 'consolidated_names',
  'OverviewOfAffiliatedEntitiesTextBlock': 'affiliated',
}
os.makedirs('data/edinet_blocks', exist_ok=True)
docs = []
with open('data/edinet_docs.jsonl', encoding='utf-8') as fh:
    for line in fh:
        d = json.loads(line)
        if d.get('docTypeCode') == '120' and (d.get('secCode') or '').strip() and (d.get('submitDateTime') or '') >= a.since:
            docs.append(d)
docs.sort(key=lambda d: d['submitDateTime'], reverse=True)
todo = [d for d in docs if not os.path.exists(f"data/edinet_blocks/{d['docID']}.json.gz")]
print(f"対象 {len(docs)} 書類 / 未取得 {len(todo)}", flush=True)
n = 0; t0 = time.time(); fail = 0
for d in todo:
    if a.limit and n >= a.limit: break
    url = f"{API}/documents/{d['docID']}?" + urllib.parse.urlencode({'type': 5, 'Subscription-Key': api_key()})
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'JP_company_vis/0.1'}), timeout=120).read()
        z = zipfile.ZipFile(io.BytesIO(raw)); names = [x for x in z.namelist() if '/jpcrp' in x and x.endswith('.csv')]
        out = {'doc': d, 'blocks': {}}
        if names:
            b = z.read(names[0]); txt = b.decode('utf-16') if b[:2] == b'\xff\xfe' else b.decode('utf-8', 'ignore')
            for r in csv.reader(io.StringIO(txt), delimiter='\t'):
                if len(r) < 9: continue
                for k, v in BLOCKS.items():
                    if r[0].endswith(':' + k) and r[2] in ('CurrentYearDuration', 'FilingDateInstant', 'CurrentYearInstant'): out['blocks'][v] = r[8]
        with gzip.open(f"data/edinet_blocks/{d['docID']}.json.gz", 'wt', encoding='utf-8') as fh: json.dump(out, fh, ensure_ascii=False)
        n += 1; fail = 0
    except Exception as e:
        fail += 1; print('ERR', d['docID'], e, flush=True)
        if fail >= 5: print('連続失敗のため停止'); sys.exit(1)
        time.sleep(5)
    if n % 200 == 0 and n: print(f"{n} 件 / 直近 {d['submitDateTime'][:10]} / {time.time()-t0:.0f}s", flush=True)
    time.sleep(a.wait)
print(f"done: {n} 件取得")
