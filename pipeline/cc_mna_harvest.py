"""Common Crawl から M&A ニュースの見出しを集める（元サイトにはアクセスしない）。
保存するのは 出典URL・取得時刻・公開日・見出し と、見出しから抽出した 買い手・対象・種別 だけ。本文は保存しない。
対象: ストライク M&Aニュース速報 / M&A Online ニュース / 日本M&Aセンター M&Aニュース（日付別一覧）
usage: python cc_mna_harvest.py [--since 2016] [--indexes N]   → data/cc_mna.jsonl (追記, URL重複はスキップ)
"""
import sys, os, json, re, html, gzip, io, time, argparse, urllib.request, urllib.parse, concurrent.futures as cf
ap = argparse.ArgumentParser(); ap.add_argument('--since', default='2016'); ap.add_argument('--indexes', type=int, default=0); ap.add_argument('--workers', type=int, default=4)
a = ap.parse_args()
OUT = 'data/cc_mna.jsonl'; DONE = 'data/cc_mna_done.txt'
UA = {'User-Agent': 'JP_company_vis/0.1 (research; contact via github.com/mattyamonaca/JP_Company_Vis)'}
def get(url, tries=4, timeout=120, headers=None):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout).read()
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(3 * (i + 1))
PATTERNS = [('strike', 'www.strike.co.jp/ma_news/detail.html?id=*'), ('maonline', 'maonline.jp/news/*'), ('nihonma', 'www.nihon-ma.co.jp/news/20*')]
indexes = [x['id'] for x in json.loads(get('https://index.commoncrawl.org/collinfo.json')) if x['id'] >= f'CC-MAIN-{a.since}']
if a.indexes: indexes = indexes[:a.indexes]
seen = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding='utf-8'): seen.add(json.loads(l)['url'])
done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
print(f"indexes {len(indexes)} / 既存 {len(seen)} 件", flush=True)

def cdx(idx, pattern):
    base = f'https://index.commoncrawl.org/{idx}-index?' + urllib.parse.urlencode({'url': pattern, 'output': 'json', 'filter': '=status:200'})
    try: pages = json.loads(get(base + '&showNumPages=true')).get('pages', 1)
    except Exception: pages = 1
    recs = []
    for p in range(pages):
        try: txt = get(base + f'&page={p}').decode()
        except Exception as e: print('CDX ERR', idx, pattern, p, e, flush=True); continue
        for l in txt.splitlines():
            if not l.strip(): continue
            try: r = json.loads(l)
            except Exception: continue          # CDX の応答行が途中で切れていることがある
            if r.get('mime', '').startswith('text/html'): recs.append(r)
        time.sleep(0.5)
    return recs
def warc_body(rec):
    off = int(rec['offset']); ln = int(rec['length'])
    raw = get('https://data.commoncrawl.org/' + rec['filename'], headers={'Range': f'bytes={off}-{off+ln-1}'})
    data = gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode('utf-8', 'ignore')
    return data.split('\r\n\r\n', 2)[-1]
strip = lambda s: html.unescape(re.sub(r'<[^>]+>', '', s)).replace('　', ' ').strip()
KIND = r'(完全子会社化|孫会社化|子会社化|持分法適用関連会社化|関連会社化|株式を取得|株式の一部を取得|株式を追加取得|株式取得|買収|吸収合併|合併|事業を譲受|事業譲受|事業を取得|出資|資本参加|資本業務提携|TOB|公開買付)'
def parse_headline(t):
    t = re.sub(r'（\d{4}/\d{2}/\d{2}）\s*$', '', t).strip()
    m = re.match(r'^(?P<buyer>[^、,，]+?)(?:＜(?P<code>[0-9A-Z]{4,5})\s*＞)?、(?P<rest>.+)$', t)
    if not m: return None
    rest = m.group('rest'); k = re.search(KIND, rest)
    if not k: return None
    target = rest[:k.start()]
    target = re.sub(r'(を|の|に)$', '', target.strip()); target = re.sub(r'^.*?の', '', target) if 'の' in target and len(target) > 25 else target
    target = target.strip('「」 ')
    return {'buyer': m.group('buyer').strip(), 'buyer_code': m.group('code'), 'target': target, 'kind': k.group(1)}
def extract(src, url, body):
    rows = []
    def meta_date():
        m = re.search(r'article:published_time"\s+content="([^"]+)', body) or re.search(r'"datePublished"\s*:\s*"([^"]+)', body)
        return m.group(1)[:10] if m else None
    if src in ('strike', 'maonline'):
        t = re.search(r'<title>(.*?)</title>', body, re.S)
        if not t: return rows
        title = strip(t.group(1)).split(' | ')[0].strip(); ph = parse_headline(title)
        d = re.search(r'（(\d{4})/(\d{2})/(\d{2})）', title); pub = f"{d.group(1)}-{d.group(2)}-{d.group(3)}" if d else meta_date()
        rows.append({'source': src, 'url': url, 'published': pub, 'title': title, **(ph or {})})
    elif src == 'nihonma':
        d = re.search(r'/news/(\d{4})/(\d{1,2})/(\d{1,2})/', url); pub = f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}" if d else None
        for m in re.finditer(r'<a[^>]+href="(https?://www\.nihon-ma\.co\.jp/news/\d{8}_[^"]+)"[^>]*>(.*?)</a>', body, re.S):
            title = strip(m.group(2))
            if not title or len(title) < 8: continue
            rows.append({'source': src, 'url': m.group(1), 'published': pub, 'title': title, 'list_url': url, **(parse_headline(title) or {})})
    return rows
out = open(OUT, 'a', encoding='utf-8'); n_new = 0
for idx in indexes:
    for src, pat in PATTERNS:
        key = f'{idx}|{src}'
        if key in done: continue
        recs = cdx(idx, pat); latest = {}
        for r in recs:
            if r['url'] in seen: continue
            y = re.search(r'(?:id=|/news/)(20\d\d)', r['url'])
            if y and y.group(1) < a.since: seen.add(r['url']); continue      # 対象期間より前の記事は取らない
            if r['url'] not in latest or r['timestamp'] > latest[r['url']]['timestamp']: latest[r['url']] = r
        todo = list(latest.values()); print(f"{idx} {src}: CDX {len(recs)} → 未取得 {len(todo)}", flush=True)
        def work(r):
            try: return r, extract(src, r['url'], warc_body(r))
            except Exception as e: return r, e
        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for r, res in ex.map(work, todo):
                if isinstance(res, Exception): print('WARC ERR', r['url'], res, flush=True); continue
                for row in res:
                    if row['url'] in seen: continue
                    seen.add(row['url']); row['captured'] = r['timestamp']; out.write(json.dumps(row, ensure_ascii=False) + '\n'); n_new += 1
                seen.add(r['url']); out.flush()
        open(DONE, 'a').write(key + '\n'); done.add(key)
print(f"done: 新規 {n_new} 件")
