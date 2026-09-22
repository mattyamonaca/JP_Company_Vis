#!/bin/sh
# 全パイプライン。引数: 法人番号全件CSV のパス
set -e
cd "$(dirname "$0")/.."
CSV="$1"; SNAP="${2:-2026-08-31}"; DB=data/venture.db
rm -f "$DB"
python3 pipeline/load_houjin.py "$CSV" "$DB" "$SNAP"
python3 pipeline/load_edinet_codelist.py data/Edinetcode.zip "$DB" "$(date +%F)"
.venv/bin/python pipeline/load_univ_startups.py data/Univ-venture_db_data.xlsx "$DB" "$(date +%F)"
python3 pipeline/tag_keywords.py "$DB"
# EDINET 書類一覧 (要 EDINET_API_KEY。縦覧期間の都合で取得できるのは直近10年分)
python3 pipeline/fetch_edinet_docs.py 2016-09-19 "$(date +%F)"
python3 pipeline/load_edinet_docs.py "$DB"
# 上場企業の有報注記 (時間がかかる。中断再開可)
python3 pipeline/fetch_edinet_blocks.py --since 2017
python3 pipeline/parse_acquisitions.py "$DB"
python3 pipeline/build_site_data.py "$DB" site/data   # site/data を作り直す (先に実行)
python3 pipeline/build_cube.py "$DB" site/data
