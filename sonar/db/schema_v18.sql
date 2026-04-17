-- ============================================================================
-- SONAR v2 · Schema v18
-- ============================================================================
-- Reference DDL for SQLite (MVP). Migration path to PostgreSQL preserved.
--
-- Organization:
--   1. Meta tables (connectors, runs, methodology versions)
--   2. Raw data audit
--   3. Cycle indicators (per-cycle components)
--   4. Sub-model outputs
--   5. Cycle scores (composite)
--   6. Integration layer (matriz 4-way, diagnostics, cost of capital)
--   7. Views for common aggregations
--
-- Conventions:
--   - country_code: ISO 3166-1 alpha-2 uppercase (PT, DE, US)
--   - currency: ISO 4217 (EUR, USD, GBP)
--   - date: ISO 8601 (YYYY-MM-DD)
--   - timestamps: UTC, ISO 8601
--   - bps columns: INTEGER or REAL, named with _bps suffix
--   - pct columns: REAL, named with _pct suffix
--   - All tables have created_at, updated_at
-- ============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================================
-- 1. META TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS connector_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_name TEXT NOT NULL,
    run_type TEXT NOT NULL,          -- 'daily', 'backfill', 'manual', 'weekly'
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'running',  -- 'running', 'success', 'partial', 'failed'
    rows_inserted INTEGER DEFAULT 0,
    rows_updated INTEGER DEFAULT 0,
    rows_skipped INTEGER DEFAULT 0,
    warnings_count INTEGER DEFAULT 0,
    error_message TEXT,
    metadata_json TEXT
);

CREATE INDEX idx_connector_runs_started ON connector_runs(connector_name, started_at DESC);

CREATE TABLE IF NOT EXISTS methodology_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,            -- e.g. 'nss_fitter', 'erp_dcf', 'crp_computation'
    version TEXT NOT NULL,            -- e.g. 'v1.2'
    effective_from DATE NOT NULL,
    effective_to DATE,
    description TEXT,
    changelog TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(module, version)
);

CREATE TABLE IF NOT EXISTS calibration_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    calibration_date DATE NOT NULL,
    parameters_json TEXT NOT NULL,    -- full calibration parameters snapshot
    methodology_version TEXT NOT NULL,
    triggering_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(module, calibration_date)
);

-- ============================================================================
-- 2. RAW DATA AUDIT
-- ============================================================================
-- Preserve raw connector outputs for auditability.
-- Cleaned periodically (e.g. >90 days purged after aggregation verified).

CREATE TABLE IF NOT EXISTS raw_data_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_name TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    data_as_of DATE,
    request_params_json TEXT,
    response_summary TEXT,            -- first ~500 chars of response
    response_hash TEXT,               -- SHA256 for dedup
    connector_run_id INTEGER,
    FOREIGN KEY (connector_run_id) REFERENCES connector_runs(id)
);

CREATE INDEX idx_raw_audit_connector_date ON raw_data_audit(connector_name, fetched_at DESC);

-- ============================================================================
-- 3. CYCLE INDICATORS (per-cycle)
-- ============================================================================
-- Store individual indicator time series grouped by cycle and component.

CREATE TABLE IF NOT EXISTS economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    component TEXT NOT NULL,          -- 'E1_activity', 'E2_leading', 'E3_labor', 'E4_sentiment'
    indicator_code TEXT NOT NULL,     -- e.g. 'GDP_QQ', 'PMI_MFG', 'UMICH_CONS'
    date DATE NOT NULL,
    value REAL NOT NULL,
    unit TEXT,                         -- 'pct_yoy', 'index', 'count_millions'
    source TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,                        -- comma-separated warning flags
    methodology_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, indicator_code, date)
);

CREATE INDEX idx_econ_ind_country_date ON economic_indicators(country_code, date);
CREATE INDEX idx_econ_ind_component ON economic_indicators(component, country_code, date);

CREATE TABLE IF NOT EXISTS credit_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    component TEXT NOT NULL,          -- 'expansion', 'leverage', 'quality', 'standards', 'spreads'
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, indicator_code, date)
);

CREATE INDEX idx_cred_ind_country_date ON credit_indicators(country_code, date);

CREATE TABLE IF NOT EXISTS monetary_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    component TEXT NOT NULL,
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, indicator_code, date)
);

CREATE INDEX idx_mon_ind_country_date ON monetary_indicators(country_code, date);

CREATE TABLE IF NOT EXISTS financial_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT,                -- NULL for global (VIX, etc.)
    market TEXT,                       -- 'US', 'EA', 'UK', 'JP', 'GLOBAL'
    component TEXT NOT NULL,          -- 'F1_valuations', 'F2_momentum', 'F3_risk', 'F4_positioning'
    indicator_code TEXT NOT NULL,
    date DATE NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    source TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(market, indicator_code, date)
);

CREATE INDEX idx_fin_ind_market_date ON financial_indicators(market, date);

-- ============================================================================
-- 4. SUB-MODEL OUTPUTS
-- ============================================================================

-- 4.1 Yield curves (NSS methodology, multiple countries)

CREATE TABLE IF NOT EXISTS yield_curves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    curve_type TEXT NOT NULL,         -- 'sovereign_nominal', 'sovereign_real', 'swap_ois', 'zero'
    methodology TEXT NOT NULL,         -- 'NSS_v1', 'spline_anderson_sleath_v1'
    nss_params_json TEXT,              -- {"beta0": ..., "beta1": ..., ..., "lambda1": ..., "lambda2": ...}
    fitted_yields_json TEXT NOT NULL,  -- {"3M": 2.68, "6M": 2.70, ..., "30Y": 3.55}
    fit_rmse_bps REAL,
    fit_max_deviation_bps REAL,
    observations_count INTEGER,
    cross_validation_json TEXT,        -- {"vs_fed_gsw_max_bps": 8.5, "vs_bundesbank_max_bps": null}
    confidence REAL DEFAULT 1.0,
    source TEXT NOT NULL,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date, curve_type, methodology)
);

CREATE INDEX idx_yc_country_date ON yield_curves(country_code, date);
CREATE INDEX idx_yc_type_date ON yield_curves(curve_type, date);

CREATE TABLE IF NOT EXISTS yield_curve_forwards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    curve_type TEXT NOT NULL,
    forwards_json TEXT NOT NULL,       -- {"1y1y": 3.85, "5y5y": 3.55, "10y10y": 3.40}
    breakeven_forwards_json TEXT,       -- real-nominal implied
    methodology_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date, curve_type)
);

-- 4.2 ERP daily (multiple markets, multiple methods)

CREATE TABLE IF NOT EXISTS erp_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,             -- 'US', 'EA', 'UK', 'JP'
    date DATE NOT NULL,
    erp_dcf_damodaran_pct REAL,
    erp_gordon_pct REAL,
    erp_simple_pct REAL,
    erp_cape_pct REAL,
    canonical_erp_pct REAL NOT NULL,
    canonical_method TEXT NOT NULL,    -- which method is the primary
    inputs_json TEXT NOT NULL,         -- snapshot of inputs used
    divergence_dcf_cape_bps REAL,      -- late-cycle signal
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(market, date)
);

CREATE INDEX idx_erp_market_date ON erp_daily(market, date);

-- 4.3 Country Risk Premium

CREATE TABLE IF NOT EXISTS sovereign_cds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    tenor TEXT NOT NULL,              -- '1Y', '3Y', '5Y', '7Y', '10Y'
    cds_bps REAL NOT NULL,
    liquidity_flag TEXT,              -- 'good', 'moderate', 'limited'
    source TEXT NOT NULL,             -- 'wgb_scrape', 'bloomberg', 'markit'
    methodology_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date, tenor, source)
);

CREATE INDEX idx_cds_country_date ON sovereign_cds(country_code, date);

CREATE TABLE IF NOT EXISTS country_risk_premium (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    default_spread_bps REAL NOT NULL,
    default_spread_source TEXT NOT NULL,  -- 'cds_5y', 'usd_sovereign', 'rating_based'
    vol_ratio REAL NOT NULL,
    vol_ratio_source TEXT NOT NULL,        -- 'country_specific', 'damodaran_default'
    crp_bps REAL NOT NULL,
    crp_range_low_bps REAL,
    crp_range_high_bps REAL,
    crp_damodaran_standard_bps REAL,      -- cross-check using 1.5x
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

CREATE INDEX idx_crp_country_date ON country_risk_premium(country_code, date);

-- 4.4 Ratings

CREATE TABLE IF NOT EXISTS sovereign_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    agency TEXT NOT NULL,             -- 'sp', 'moodys', 'fitch', 'dbrs'
    date DATE NOT NULL,               -- effective date of this rating state
    rating TEXT NOT NULL,
    outlook TEXT,                      -- 'stable', 'positive', 'negative', 'developing', 'watch'
    rating_type TEXT NOT NULL DEFAULT 'foreign_currency',  -- 'foreign_currency', 'local_currency'
    sonar_notch REAL NOT NULL,         -- 0-21 common scale
    sonar_notch_outlook_adjusted REAL,
    last_action_type TEXT,             -- 'upgrade', 'downgrade', 'affirmed', 'outlook_change'
    last_action_date DATE,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, agency, date, rating_type)
);

CREATE INDEX idx_ratings_country_date ON sovereign_ratings(country_code, date);
CREATE INDEX idx_ratings_agency_date ON sovereign_ratings(agency, date);

-- 4.5 Rating-to-spread mapping (versioned table)

CREATE TABLE IF NOT EXISTS rating_spread_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sonar_notch INTEGER NOT NULL,
    rating_equivalent TEXT NOT NULL,
    spread_central_bps INTEGER NOT NULL,
    spread_range_low_bps INTEGER NOT NULL,
    spread_range_high_bps INTEGER NOT NULL,
    spread_extended_low_bps INTEGER,
    spread_extended_high_bps INTEGER,
    calibration_date DATE NOT NULL,
    calibration_window_years INTEGER DEFAULT 5,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sonar_notch, calibration_date)
);

CREATE INDEX idx_rsm_notch_date ON rating_spread_mapping(sonar_notch, calibration_date);

-- 4.6 Expected inflation

CREATE TABLE IF NOT EXISTS expected_inflation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    tenor TEXT NOT NULL,              -- '1Y', '2Y', '5Y', '5y5y_fwd', '10Y', '30Y'
    value_pct REAL NOT NULL,
    confidence_interval_low_pct REAL,
    confidence_interval_high_pct REAL,
    source TEXT NOT NULL,              -- 'market_bei', 'inflation_swap', 'survey', 'consensus', 'synthesized'
    components_json TEXT,               -- raw components used in synthesis
    anchor_status TEXT,                 -- 'well_anchored', 'moderately_anchored', 'drifting', 'unanchored'
    bc_target_pct REAL,
    drift_vs_target_pp REAL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date, tenor)
);

CREATE INDEX idx_exp_inf_country_date ON expected_inflation(country_code, date);

-- ============================================================================
-- 5. CYCLE SCORES (COMPOSITE)
-- ============================================================================

CREATE TABLE IF NOT EXISTS economic_cycle_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    ecs_score REAL NOT NULL,
    e1_activity REAL,
    e2_leading REAL,
    e3_labor REAL,
    e4_sentiment REAL,
    state TEXT NOT NULL,               -- 'Expansion', 'PeakZone', 'EarlyRecession', 'Recession'
    stagflation_overlay_active BOOLEAN DEFAULT 0,
    stagflation_score REAL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

CREATE INDEX idx_ecs_country_date ON economic_cycle_score(country_code, date);

CREATE TABLE IF NOT EXISTS credit_cycle_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    cccs_score REAL NOT NULL,
    expansion_component REAL,
    leverage_component REAL,
    quality_component REAL,
    standards_component REAL,
    spreads_component REAL,
    state TEXT NOT NULL,               -- 'Repair', 'Recovery', 'Boom', 'Speculation', 'Distress'
    boom_overlay_active BOOLEAN DEFAULT 0,
    minsky_phase TEXT,                  -- 'hedge', 'speculative', 'ponzi'
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

CREATE TABLE IF NOT EXISTS monetary_stance_composite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    msc_score REAL NOT NULL,
    policy_rate_component REAL,
    yield_curve_slope_component REAL,
    balance_sheet_component REAL,
    guidance_component REAL,
    real_rates_component REAL,
    state TEXT NOT NULL,               -- 'Accommodative', 'Neutral', 'Tight'
    dilemma_overlay_active BOOLEAN DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

CREATE TABLE IF NOT EXISTS financial_cycle_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT,                -- NULL for global
    market TEXT NOT NULL,              -- 'US', 'EA', 'UK', 'JP', 'GLOBAL'
    date DATE NOT NULL,
    fcs_score REAL NOT NULL,
    f1_valuations REAL,
    f2_momentum REAL,
    f3_risk_appetite REAL,
    f4_positioning REAL,
    state TEXT NOT NULL,               -- 'Stress', 'Caution', 'Optimism', 'Euphoria'
    bubble_warning_overlay_active BOOLEAN DEFAULT 0,
    bis_credit_gap_pp REAL,
    bis_property_gap_pct REAL,
    confidence REAL DEFAULT 1.0,
    flags TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(market, date)
);

-- ============================================================================
-- 6. INTEGRATION LAYER
-- ============================================================================

CREATE TABLE IF NOT EXISTS sonar_integrated_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    ecs_score REAL,
    cccs_score REAL,
    msc_score REAL,
    fcs_score REAL,
    matriz_4way_classification TEXT,
    matriz_4way_type TEXT,             -- 'canonical' or 'critical'
    matriz_4way_pattern_number INTEGER,
    matriz_4way_confidence REAL,
    overlays_active_json TEXT,          -- ["stagflation", "boom"]
    alert_level TEXT,                   -- 'green', 'yellow', 'orange', 'red'
    transition_probabilities_json TEXT,
    confidence REAL DEFAULT 1.0,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date)
);

CREATE INDEX idx_integrated_country_date ON sonar_integrated_state(country_code, date);

CREATE TABLE IF NOT EXISTS applied_diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT,                -- NULL for global
    market TEXT,
    date DATE NOT NULL,
    bubble_score REAL,
    bubble_components_json TEXT,
    risk_appetite_regime TEXT,        -- 'R1_fear', 'R2_cautious', 'R3_normal', 'R4_euphoric'
    risk_appetite_score REAL,
    real_estate_phase TEXT,
    real_estate_components_json TEXT,
    minsky_fragility_score REAL,
    minsky_phase TEXT,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, market, date)
);

CREATE TABLE IF NOT EXISTS cost_of_capital_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    date DATE NOT NULL,
    currency TEXT NOT NULL,
    risk_free_pct REAL NOT NULL,
    risk_free_benchmark TEXT NOT NULL, -- 'bund_10y', 'ust_10y', 'jgb_10y'
    erp_mature_pct REAL NOT NULL,
    beta REAL DEFAULT 1.0,
    crp_bps REAL,
    cost_of_equity_nominal_pct REAL NOT NULL,
    cost_of_equity_real_pct REAL,
    expected_inflation_pct REAL,
    methodology_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, date, currency)
);

CREATE INDEX idx_coc_country_date ON cost_of_capital_daily(country_code, date);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,         -- 'threshold_breach', 'regime_shift', 'rating_action', 'cross_validation_fail'
    severity TEXT NOT NULL,            -- 'info', 'warning', 'critical'
    country_code TEXT,
    market TEXT,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    data_json TEXT,
    editorial_angle_template TEXT,    -- reference to templates/...
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX idx_alerts_triggered ON alerts(triggered_at DESC);
CREATE INDEX idx_alerts_severity ON alerts(severity, triggered_at DESC);

-- ============================================================================
-- 7. VIEWS
-- ============================================================================

CREATE VIEW IF NOT EXISTS v_latest_cycle_states_per_country AS
SELECT
    country_code,
    date,
    ecs_score,
    cccs_score,
    msc_score,
    fcs_score,
    matriz_4way_classification,
    overlays_active_json,
    alert_level
FROM sonar_integrated_state
WHERE (country_code, date) IN (
    SELECT country_code, MAX(date)
    FROM sonar_integrated_state
    GROUP BY country_code
);

CREATE VIEW IF NOT EXISTS v_cost_of_capital_latest AS
SELECT
    c.country_code,
    c.date,
    c.currency,
    c.risk_free_pct,
    c.erp_mature_pct,
    c.crp_bps,
    c.cost_of_equity_nominal_pct,
    c.cost_of_equity_real_pct,
    c.expected_inflation_pct
FROM cost_of_capital_daily c
INNER JOIN (
    SELECT country_code, currency, MAX(date) as latest
    FROM cost_of_capital_daily
    GROUP BY country_code, currency
) latest_dates
  ON c.country_code = latest_dates.country_code
 AND c.currency = latest_dates.currency
 AND c.date = latest_dates.latest;

CREATE VIEW IF NOT EXISTS v_rating_consolidated_latest AS
SELECT
    country_code,
    MAX(CASE WHEN agency = 'sp' THEN rating END) as sp_rating,
    MAX(CASE WHEN agency = 'moodys' THEN rating END) as moodys_rating,
    MAX(CASE WHEN agency = 'fitch' THEN rating END) as fitch_rating,
    MAX(CASE WHEN agency = 'dbrs' THEN rating END) as dbrs_rating,
    AVG(sonar_notch_outlook_adjusted) as sonar_notch_avg,
    MAX(date) as as_of_date
FROM sonar_ratings
WHERE rating_type = 'foreign_currency'
GROUP BY country_code;

-- ============================================================================
-- END OF SCHEMA v18
-- ============================================================================
