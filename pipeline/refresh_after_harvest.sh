#!/bin/sh
# 有報注記と Common Crawl の収集が両方終わるのを待ってから、ラベル付与→サイトデータ再生成→push を行う
cd "$(dirname "$0")/.."
while pgrep -f fetch_edinet_blocks.py >/dev/null || pgrep -f cc_mna_harvest.py >/dev/null; do sleep 60; done
python3 pipeline/parse_acquisitions.py data/venture.db && python3 pipeline/load_cc_mna.py data/venture.db \
 && python3 pipeline/build_site_data.py data/venture.db site/data && python3 pipeline/build_cube.py data/venture.db site/data \
 && git add -A site/data && git commit -q -m "Regenerate labels after the annual-report and Common Crawl harvests completed

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push 2>&1 | tail -1
echo "refresh done $(date)"
