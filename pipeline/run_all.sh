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
python3 pipeline/build_site_data.py "$DB" site/data
