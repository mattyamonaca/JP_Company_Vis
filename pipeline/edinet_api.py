"""EDINET API v2 の薄いクライアント。
APIキーは環境変数 EDINET_API_KEY → ~/.persona/.env の順で探す (jp_market_vis と同じ規約)。キーの値は出力しない。
usage: python edinet_api.py check
"""
import os, sys, json, time, urllib.request, urllib.parse
API = "https://api.edinet-fsa.go.jp/api/v2"

def api_key():
    k = os.environ.get("EDINET_API_KEY", "").strip()
    if k: return k
    p = os.path.expanduser("~/.persona/.env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.startswith("EDINET_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("EDINET_API_KEY が見つかりません (環境変数 or ~/.persona/.env)")

def documents(date, retries=3):
    """指定日の提出書類一覧 (type=2: メタデータあり)。"""
    url = f"{API}/documents.json?" + urllib.parse.urlencode({"date": date, "type": 2, "Subscription-Key": api_key()})
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "JP_company_vis/0.1"}), timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == retries - 1: raise
            time.sleep(2 * (i + 1))

if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:
        d = documents("2026-09-18"); m = d.get("metadata", {})
        docs = d.get("results", [])
        print("status", m.get("status"), m.get("message"), "| 件数", m.get("resultset", {}).get("count"))
        ipo = [x for x in docs if x.get("docTypeCode") == "030" and "新規公開" in (x.get("docDescription") or "")]
        print("有価証券届出書(新規公開時)", len(ipo), [(x["filerName"], x["submitDateTime"]) for x in ipo][:3])
        tob = [x for x in docs if x.get("docTypeCode") == "240"]
        print("公開買付届出書", len(tob), [(x["filerName"], x.get("subjectEdinetCode")) for x in tob][:3])
