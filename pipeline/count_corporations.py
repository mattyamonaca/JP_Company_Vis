import csv, sys, collections, json
f = sys.argv[1]
KIND = {'101':'国の機関','201':'地方公共団体','301':'株式会社','302':'有限会社','303':'合名会社','304':'合資会社','305':'合同会社','399':'その他の設立登記法人','401':'外国会社等','499':'その他'}
by_year_kind = collections.Counter()          # (year, kind) -> count
closed_by_year_kind = collections.Counter()   # (year, kind) -> closed count
close_reason = collections.Counter()          # (year, kind, reason)
proc = collections.Counter(); latest = collections.Counter()
by_month = collections.Counter()              # (yyyy-mm, kind) for 301/305
n=0
with open(f, encoding='utf-8', newline='') as fh:
    for r in csv.reader(fh):
        n+=1
        kind = r[8]; assign = r[22]; closed_date = r[18]; reason = r[19]
        proc[r[2]]+=1; latest[r[23]]+=1
        y = assign[:4]
        if assign == '2015-10-05': y = '2015-10-05(一括指定)'
        by_year_kind[(y,kind)]+=1
        if kind in ('301','305'): by_month[(assign[:7],kind)]+=1
        if closed_date:
            closed_by_year_kind[(y,kind)]+=1
            close_reason[(y,kind,reason)]+=1
print("rows",n); print("処理区分",dict(proc)); print("最新履歴",dict(latest))
json.dump({'by_year_kind':{f"{k[0]}|{k[1]}":v for k,v in by_year_kind.items()},
           'closed':{f"{k[0]}|{k[1]}":v for k,v in closed_by_year_kind.items()},
           'reason':{f"{k[0]}|{k[1]}|{k[2]}":v for k,v in close_reason.items()},
           'by_month':{f"{k[0]}|{k[1]}":v for k,v in by_month.items()}}, open('agg.json','w'), ensure_ascii=False)
years = sorted({k[0] for k in by_year_kind})
kinds = ['301','305','303','304','302','399','401','499','101','201']
print("\n指定年 | " + " | ".join(KIND[k] for k in kinds) + " | 合計 | うち閉鎖済")
for y in years:
    row=[by_year_kind[(y,k)] for k in kinds]
    tot=sum(by_year_kind[(y,k)] for k in KIND); cl=sum(closed_by_year_kind[(y,k)] for k in KIND)
    print(y, "|", " | ".join(str(x) for x in row), "|", tot, "|", cl)
