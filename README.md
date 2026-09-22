# JP_Company_Vis — 日本の新設法人ライフサイクル

2016年以降に設立された日本の会社の「一生」（設立 → 存続 → 清算 / 合併 / 上場）を、無料の公的データだけで可視化する完全静的サイト。

- 企業検索はなし。事前集計したサマリーと、カテゴリ別の企業一覧のみ。
- データ: 国税庁 法人番号 全件データ、金融庁 EDINETコードリスト、経産省 大学発ベンチャーデータベース（いずれも PDL1.0 / CC BY 4.0互換）。
- ホスティング: Cloudflare Pages（`site/` をそのまま配信）。

## 構成

```
pipeline/  データ取り込みと集計 (Python 3 標準ライブラリ + openpyxl)
  schema.sql              SQLite スキーマ（法人マスタ / 生データ / スナップショット / 派生）
  load_houjin.py          法人番号 全件CSV → company, agg_year_kind, agg_year_pref
  load_edinet_codelist.py EDINETコードリスト → 上場区分・33業種タグ
  load_univ_startups.py   大学発ベンチャーDB(Excel) → 属性・技術分野タグ
  tag_keywords.py         商号キーワード → tier3 タグ
  build_site_data.py      SQLite → site/data/*.json
  run_all.sh              上記を順に実行
site/      静的サイト (HTML + ES modules、ビルド不要)
  data/    生成物（集計JSON、カテゴリ別一覧）
```

## 再生成

```sh
python3 -m venv .venv && .venv/bin/pip install openpyxl
# 法人番号公表サイト > ダウンロード > 全件データ > 全国 (CSV Unicode) を取得して展開
# https://www.houjin-bangou.nta.go.jp/download/zenken/
curl -L -o data/Edinetcode.zip https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip
curl -L -o data/Univ-venture_db_data.xlsx https://www.meti.go.jp/policy/innovation_corp/excel/Univ-venture_db_data.xlsx
pipeline/run_all.sh /path/to/00_zenkoku_all_YYYYMMDD.csv YYYY-MM-DD
python3 -m http.server -d site 8000
```

## 業種タグの3層

| tier | 根拠 | 例 |
|---|---|---|
| 1 | 公的コードで確定 | EDINET 提出者業種、上場区分、閉鎖事由 |
| 2 | 公的文書から推定 | 大学発ベンチャーDBの技術分野 |
| 3 | 商号キーワード | 「建設」「不動産」などを含む商号（精度低） |

## 出典表示

出典：国税庁法人番号公表サイト（国税庁）、EDINET閲覧（提出）サイト（金融庁）、大学発ベンチャーデータベース（経済産業省）を加工して作成。
