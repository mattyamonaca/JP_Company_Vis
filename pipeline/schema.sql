-- ============================================================
-- 日本のベンチャー企業ライフサイクルDB  スキーマ v0.1
-- 主キーは全テーブルで法人番号(13桁)。SQLite / DuckDB 両対応の素朴なSQL。
-- 層構成:
--   0. provenance : 出典・ライセンス（CC BY表示のため必須）
--   1. master     : 法人マスタ（国税庁 法人番号 全件データ）
--   2. raw_*      : ソースごとの生データ（取得したまま。加工しない）
--   3. snapshot_* : 時系列で差分を取るための定点観測テーブル
--   4. derived    : イベント（タイムライン）、タグ、名寄せ、母集団フラグ
-- ============================================================

-- ---------- 0. provenance ----------
CREATE TABLE IF NOT EXISTS source (
  source_id        TEXT PRIMARY KEY,      -- 'nta_houjin', 'gbiz', 'edinet', 'meti_univ', 'fsa_license', 'geps', 'shokuba'
  publisher        TEXT NOT NULL,         -- 国税庁 / 経済産業省 / 金融庁 ...
  title            TEXT NOT NULL,
  url              TEXT NOT NULL,
  license          TEXT NOT NULL,         -- 'PDL1.0' / 'CC BY 4.0 互換' / '独自規約'
  attribution_text TEXT NOT NULL,         -- 画面に出す「出典：…」の定型文
  notes            TEXT                   -- 目的制限・API文言などの注意
);

CREATE TABLE IF NOT EXISTS ingest_run (
  run_id        INTEGER PRIMARY KEY,
  source_id     TEXT NOT NULL REFERENCES source(source_id),
  snapshot_date TEXT NOT NULL,            -- データ側の基準日 (例: 全件データの 2026-08-31)
  retrieved_at  TEXT NOT NULL,            -- 取得日時
  file_name     TEXT,
  row_count     INTEGER
);

-- ---------- 1. master ----------
-- 国税庁 法人番号 全件データ (30列) をほぼそのまま保持。列名は リソース定義書 に対応。
CREATE TABLE IF NOT EXISTS company (
  houjin_bangou      TEXT PRIMARY KEY,    -- 法人番号
  name               TEXT NOT NULL,       -- 商号又は名称
  name_kana          TEXT,                -- フリガナ
  name_en            TEXT,                -- 商号又は名称(英語)
  kind_code          TEXT NOT NULL,       -- 法人種別 301 株式会社 / 305 合同会社 / 399 その他設立登記法人 ...
  pref_code          TEXT,                -- 都道府県コード
  city_code          TEXT,                -- 市区町村コード
  pref               TEXT,
  city               TEXT,
  street             TEXT,                -- 丁目番地等
  postal_code        TEXT,
  address_overseas   TEXT,                -- 国外所在地
  assigned_on        TEXT NOT NULL,       -- 法人番号指定年月日  ※2015-10-05 は既存法人の一括指定
  is_bulk_assigned   INTEGER NOT NULL,    -- 1 = 2015-10-05 一括指定 (設立日として使えない)
  changed_on         TEXT,                -- 変更年月日 (直近の変更)
  updated_on         TEXT,                -- 更新年月日
  process_code       TEXT,                -- 処理区分 01 新規 / 11 商号変更 / 12 所在地変更 / 21 閉鎖 / 22 復活 ...
  change_detail      TEXT,                -- 変更事由の詳細
  closed_on          TEXT,                -- 登記記録の閉鎖等年月日
  close_reason_code  TEXT,                -- 01 清算の結了等 / 11 合併による解散等 / 21 登記官による閉鎖 / 31 その他
  successor_houjin_bangou TEXT,           -- 承継先法人番号 (合併時)
  search_excluded    INTEGER,             -- 検索対象除外
  snapshot_date      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_company_assigned ON company(assigned_on);
CREATE INDEX IF NOT EXISTS ix_company_kind     ON company(kind_code);
CREATE INDEX IF NOT EXISTS ix_company_name     ON company(name);
CREATE INDEX IF NOT EXISTS ix_company_closed   ON company(closed_on);

-- 商号・所在地・閉鎖の履歴。全件データは最新状態しか持たないので、
-- 日次差分データ(処理区分付き)を毎日取り込んで積み上げる。
CREATE TABLE IF NOT EXISTS company_change (
  houjin_bangou   TEXT NOT NULL,
  changed_on      TEXT NOT NULL,
  process_code    TEXT NOT NULL,          -- 11 商号変更 / 12 所在地変更 / 21 閉鎖 / 22 復活 / 71 吸収合併 ...
  name_after      TEXT,
  address_after   TEXT,
  change_detail   TEXT,
  run_id          INTEGER REFERENCES ingest_run(run_id),
  PRIMARY KEY (houjin_bangou, changed_on, process_code)
);

-- ---------- 2. raw_* (Gビズインフォ 一括DLの種別にそのまま対応) ----------
CREATE TABLE IF NOT EXISTS raw_gbiz_basic (
  houjin_bangou    TEXT PRIMARY KEY,
  industry_code    TEXT,                  -- 業種コード (日本標準産業分類 大分類)
  business_summary TEXT,                  -- 事業概要
  employee_number  INTEGER,
  capital_stock    INTEGER,
  founded_on       TEXT,                  -- 設立年月日 (GEPS等由来。法人番号指定日より信頼できる場合がある)
  founding_year    INTEGER,               -- 創業年
  company_url      TEXT,
  representative   TEXT,
  company_size     TEXT,                  -- 企業規模詳細
  update_date      TEXT,
  run_id           INTEGER REFERENCES ingest_run(run_id)
);

CREATE TABLE IF NOT EXISTS raw_gbiz_subsidy (       -- 補助金情報
  houjin_bangou TEXT NOT NULL, title TEXT, amount INTEGER, date_of_approval TEXT,
  government_department TEXT, target TEXT, note TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_gbiz_certification ( -- 届出・認定情報 (許認可・DX認定・経営革新など)
  houjin_bangou TEXT NOT NULL, title TEXT, date_of_approval TEXT, category TEXT,
  government_department TEXT, enterprise_scale TEXT, expiration_date TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_gbiz_commendation (  -- 表彰情報
  houjin_bangou TEXT NOT NULL, title TEXT, date_of_commendation TEXT, category TEXT,
  government_department TEXT, target TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_gbiz_procurement (   -- 調達情報
  houjin_bangou TEXT NOT NULL, title TEXT, amount INTEGER, date_of_order TEXT,
  government_department TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_gbiz_patent (        -- 特許・意匠・商標 (特許庁データをGビズインフォ経由で)
  houjin_bangou TEXT NOT NULL, patent_type TEXT,    -- 特許 / 意匠 / 商標
  application_number TEXT, application_date TEXT, title TEXT,
  classification TEXT,                              -- IPC / 商標区分
  run_id INTEGER,
  PRIMARY KEY (houjin_bangou, patent_type, application_number)
);
CREATE TABLE IF NOT EXISTS raw_gbiz_finance (       -- 財務情報 (EDINET有報由来、上場企業のみ)
  houjin_bangou TEXT NOT NULL, fiscal_year_end TEXT, net_sales INTEGER, operating_income INTEGER,
  net_income INTEGER, total_assets INTEGER, net_assets INTEGER, employee_number INTEGER,
  accounting_standard TEXT, run_id INTEGER,
  PRIMARY KEY (houjin_bangou, fiscal_year_end)
);
CREATE TABLE IF NOT EXISTS raw_gbiz_workplace (     -- 職場情報 (しょくばらぼ由来)
  houjin_bangou TEXT PRIMARY KEY, industry TEXT, employee_number INTEGER,
  average_age REAL, average_years_of_service REAL, female_ratio REAL,
  paid_leave_rate REAL, overtime_hours REAL, run_id INTEGER
);

-- EDINET
CREATE TABLE IF NOT EXISTS raw_edinet_document (    -- 書類一覧API (docID単位)
  doc_id            TEXT PRIMARY KEY,
  edinet_code       TEXT,
  houjin_bangou     TEXT,                 -- 提出者法人番号 (コードリストで補完)
  filer_name        TEXT,
  doc_type_code     TEXT,                 -- 030 有価証券届出書 / 120 有価証券報告書 / 240 公開買付届出書 / 350 大量保有報告書 ...
  form_code         TEXT,
  submit_datetime   TEXT,
  period_start      TEXT, period_end TEXT,
  subject_edinet_code TEXT,               -- 公開買付・大量保有の対象会社
  doc_description   TEXT,
  is_ipo_filing     INTEGER,              -- 有価証券届出書(新規公開時) なら1
  run_id            INTEGER
);
CREATE INDEX IF NOT EXISTS ix_edinet_doc_hb ON raw_edinet_document(houjin_bangou, submit_datetime);

-- 経産省・金融庁・調達ポータルの一覧 (法人番号なしのものは name_match で名寄せ)
CREATE TABLE IF NOT EXISTS raw_meti_univ_startup (
  record_id TEXT PRIMARY KEY, company_name TEXT NOT NULL, university TEXT, field TEXT,
  founded_year INTEGER, pref TEXT, survey_year INTEGER, houjin_bangou TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_jstartup (
  record_id TEXT PRIMARY KEY, company_name TEXT NOT NULL, selection_round TEXT,
  selected_year INTEGER, region_program TEXT, houjin_bangou TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_fsa_license (
  record_id TEXT PRIMARY KEY, company_name TEXT NOT NULL, license_type TEXT NOT NULL,
  registration_number TEXT, registered_on TEXT, bureau TEXT, houjin_bangou TEXT, run_id INTEGER
);
CREATE TABLE IF NOT EXISTS raw_geps_qualification (   -- 全省庁統一資格 有資格者名簿
  houjin_bangou TEXT NOT NULL, vendor_code TEXT, qualification_type TEXT, grade TEXT,
  business_item TEXT, valid_period TEXT, run_id INTEGER
);

-- ---------- 3. snapshot_* (定点観測。差分から「イベント」を作る) ----------
CREATE TABLE IF NOT EXISTS snapshot_edinet_filer (  -- EDINETコードリストを日次で保存 → 上場/非上場の変化を検出
  snapshot_date  TEXT NOT NULL,
  edinet_code    TEXT NOT NULL,
  houjin_bangou  TEXT,
  filer_name     TEXT,
  filer_type     TEXT,
  listing_status TEXT,                    -- '上場' / '非上場' / ''
  industry_jpx33 TEXT,                    -- 提出者業種 (33業種)
  sec_code       TEXT,
  capital        INTEGER,
  fiscal_year_end TEXT,
  PRIMARY KEY (snapshot_date, edinet_code)
);
CREATE TABLE IF NOT EXISTS snapshot_establishment ( -- Gビズインフォ 事業所情報 (年金機構由来) を月次で保存 → 従業員数推移
  snapshot_date   TEXT NOT NULL,
  houjin_bangou   TEXT NOT NULL,
  establishment_name TEXT NOT NULL,
  address         TEXT,
  insured_count   INTEGER,                -- 被保険者数
  loss_date       TEXT,                   -- 全喪年月日
  PRIMARY KEY (snapshot_date, houjin_bangou, establishment_name)
);

-- ---------- 4. derived ----------
-- 名寄せ: 法人番号を持たないソースのレコードを法人番号に対応付ける
CREATE TABLE IF NOT EXISTS name_match (
  source_id        TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_name      TEXT NOT NULL,
  normalized_name  TEXT NOT NULL,         -- NFKC + 空白除去 + 小文字化 + 法人格除去
  houjin_bangou    TEXT,                  -- NULL = 未解決
  match_method     TEXT,                  -- exact / exact+pref / manual
  candidate_count  INTEGER,               -- 同名法人数 (>1 なら要確認)
  is_ambiguous     INTEGER,
  PRIMARY KEY (source_id, source_record_id)
);

-- タイムライン: 全ソースのイベントを1本に統合 (画面の主役)
CREATE TABLE IF NOT EXISTS lifecycle_event (
  event_id       INTEGER PRIMARY KEY,
  houjin_bangou  TEXT NOT NULL,
  event_date     TEXT NOT NULL,
  event_type     TEXT NOT NULL,           -- founded / renamed / relocated / closed_liquidation / closed_merger /
                                          -- ipo_filing / listed / delisted / tob_target / major_holder /
                                          -- subsidy / certification / commendation / patent / trademark /
                                          -- univ_startup / jstartup / license
  event_subtype  TEXT,                    -- 例: closed_merger の 承継先, delisted の理由
  title          TEXT NOT NULL,
  related_houjin_bangou TEXT,             -- 合併先・買収者など相手方
  detail_json    TEXT,
  source_id      TEXT NOT NULL REFERENCES source(source_id),
  source_ref     TEXT,                    -- docID / 出願番号 / 行ID
  source_url     TEXT
);
CREATE INDEX IF NOT EXISTS ix_event_hb   ON lifecycle_event(houjin_bangou, event_date);
CREATE INDEX IF NOT EXISTS ix_event_type ON lifecycle_event(event_type, event_date);

-- タグ: 3層 (tier 1 公的コードで確定 / 2 公的文書から推定 / 3 商号キーワード)
CREATE TABLE IF NOT EXISTS company_tag (
  houjin_bangou TEXT NOT NULL,
  tag_type      TEXT NOT NULL,            -- industry_jsic_major / industry_jpx33 / license / trademark_class / ipc / field / keyword
  tag_value     TEXT NOT NULL,            -- コード
  tag_label     TEXT NOT NULL,            -- 表示名
  tier          INTEGER NOT NULL,         -- 1 / 2 / 3
  confidence    REAL,
  source_id     TEXT NOT NULL,
  evidence_ref  TEXT,
  PRIMARY KEY (houjin_bangou, tag_type, tag_value, source_id)
);
CREATE INDEX IF NOT EXISTS ix_tag_type ON company_tag(tag_type, tag_value);

-- 母集団フラグ: 「ベンチャーらしさ」の根拠を列ごとに持つ (集計の絞り込みに使う)
CREATE TABLE IF NOT EXISTS company_scope (
  houjin_bangou       TEXT PRIMARY KEY,
  cohort_year         INTEGER,            -- 指定年 (一括指定は NULL)
  is_company          INTEGER,            -- 301-305
  founded_2016plus    INTEGER,
  has_trademark       INTEGER,
  has_patent          INTEGER,
  has_workplace_info  INTEGER,
  has_subsidy         INTEGER,
  is_univ_startup     INTEGER,
  is_jstartup         INTEGER,
  has_ipo_filing      INTEGER,
  is_listed           INTEGER,
  venture_score       INTEGER             -- 上のフラグの合計 (暫定)
);

-- 便利ビュー: コホート別の生存状況
CREATE VIEW IF NOT EXISTS v_cohort_survival AS
SELECT substr(assigned_on,1,4) AS cohort_year,
       kind_code,
       COUNT(*)                                   AS founded,
       SUM(closed_on IS NOT NULL AND closed_on<>'') AS closed,
       SUM(close_reason_code='01')                 AS closed_liquidation,
       SUM(close_reason_code='11')                 AS closed_merger,
       SUM(close_reason_code='21')                 AS closed_by_registrar
FROM company
WHERE is_bulk_assigned=0
GROUP BY 1,2;
