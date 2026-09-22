"""SQLite → site/data/cube.json
2016年以降設立の会社を「属性の組み合わせ × 社数」に畳む。トップページの絞り込み（ファセット）用。
行: [設立年idx, 都道府県idx, 法人種別idx, 状態idx, 閉鎖年idx, フラグ(bit0 上場, bit1 大学発), 商号KWビット, EDINET業種idx, 技術分野idx, 社数]
usage: python build_cube.py <db_path> <site/data dir>
"""
import sys, sqlite3, json, os, collections
db_path, out = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db_path)
PREF = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
YEARS = [str(y) for y in range(2016, 2027)]
KINDS = [('301', '株式会社'), ('305', '合同会社'), ('303', '合名会社'), ('304', '合資会社'), ('302', '有限会社')]
STATUS = [('A', '存続（登記あり）'), ('L', '清算結了'), ('M', '合併で消滅'), ('R', '登記官による閉鎖'), ('O', 'その他の閉鎖')]
kind_ix = {k: i for i, (k, _) in enumerate(KINDS)}
# タグ辞書
kw = [r for r in con.execute("SELECT DISTINCT tag_value, tag_label FROM company_tag WHERE tag_type='keyword' ORDER BY tag_value")]
kw_ix = {v: i for i, (v, _) in enumerate(kw)}
jpx = [r[0] for r in con.execute("SELECT tag_value FROM company_tag WHERE tag_type='industry_jpx33' GROUP BY 1 ORDER BY COUNT(*) DESC")]
jpx_ix = {v: i + 1 for i, v in enumerate(jpx)}          # 0 = なし
fld = [r[0] for r in con.execute("SELECT tag_value FROM company_tag WHERE tag_type='field' GROUP BY 1 ORDER BY COUNT(*) DESC")]
fld_ix = {v: i + 1 for i, v in enumerate(fld)}
tags = collections.defaultdict(lambda: [0, 0, 0])      # hb -> [kwmask, jpx, field]
for hb, t, v in con.execute("SELECT houjin_bangou, tag_type, tag_value FROM company_tag"):
    if t == 'keyword': tags[hb][0] |= 1 << kw_ix[v]
    elif t == 'industry_jpx33': tags[hb][1] = jpx_ix[v]
    elif t == 'field': tags[hb][2] = fld_ix[v]
scope = {hb: (l or 0, u or 0) for hb, l, u in con.execute("SELECT houjin_bangou, is_listed, is_univ_startup FROM company_scope")}
def status(closed, reason):
    if not closed: return 0
    return {'01': 1, '11': 2, '21': 3}.get(reason, 4)
cube = collections.Counter(); n = 0
for hb, a, pref, kind, closed, reason in con.execute("""SELECT houjin_bangou, assigned_on, pref_code, kind_code, closed_on, close_reason_code
      FROM company WHERE assigned_on>='2016-01-01' AND kind_code IN ('301','302','303','304','305')"""):
    n += 1
    y = int(a[:4]) - 2016
    p = int(pref) - 1 if pref and pref.isdigit() and 1 <= int(pref) <= 47 else 47   # 47 = 不明/国外
    cy = (int(closed[:4]) - 2015) if closed else 0                                    # 0 = 閉鎖なし, 1 = 2015 ...
    l, u = scope.get(hb, (0, 0)); flags = (1 if l else 0) | (2 if u else 0)
    km, j, f = tags.get(hb, (0, 0, 0))
    cube[(y, p, kind_ix[kind], status(closed, reason), cy, flags, km, j, f)] += 1
rows = [list(k) + [v] for k, v in cube.items()]
rows.sort()
obj = {'total': n, 'dims': {
    'year': YEARS, 'pref': PREF + ['不明・国外'], 'kind': [k[1] for k in KINDS], 'status': [s[1] for s in STATUS],
    'closed_year': ['閉鎖なし'] + [str(2015 + i) for i in range(1, 12)],
    'flags': ['上場している', '大学発ベンチャー'], 'kw': [k[1] for k in kw], 'jpx': ['（上場企業以外）'] + jpx, 'field': ['（大学発以外）'] + fld},
    'rows': rows}
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, 'cube.json'), 'w', encoding='utf-8') as fh: json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'))
print(f"会社 {n} 社 → セル {len(rows)} 行, {os.path.getsize(os.path.join(out,'cube.json'))/1e6:.1f} MB")
