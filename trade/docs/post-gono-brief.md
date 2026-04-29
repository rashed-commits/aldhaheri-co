# Post Go/No-Go Upgrades — Implementation Brief

## Status

- **Saved:** 2026-04-29
- **May 10 go/no-go gate:** CANCELLED (mid-evaluation; paper-trading window Apr 14 – May 9 was not allowed to complete).
- **Authorisation:** User-instructed proceed-immediately on 2026-04-29.

## Operational Gating (set 2026-04-29)

- **Tier 1 — proceed immediately:** P1 (Finnhub), P5 (Position Sizing), P6 (FinBERT trigger).
- **Tier 2 — proceed only after P1 is confirmed clean:** P2 (Russell Screener), P3 (Committee), P4 (Earnings Calendar).
- Verify current ticker count in `src/config.py` before starting P2 — do not assume 14. (Verified at brief time: **16 tickers**.)
- Begin with P1. Report back after each proposal as specified.

## Corrections Applied to the Original Brief

- Proposal 3: model ID updated from `claude-sonnet-4-20250514` → `claude-sonnet-4-6`.

---

# Implementation Brief — Post Go/No-Go Upgrades

The go/no-go review passed on May 10. Proceed with all six proposals in priority order. Each proposal must be implemented, tested, and confirmed before moving to the next. Report back after each one — do not implement all six in one session.

---

## Ground Rules (Non-Negotiable)

- Any config change reported at time of implementation — never retrospectively
- No proposal deviates from the spec below without explicit approval
- deploy.sh is banned — manual commit + deploy only
- After each proposal: run a dry-run test, report results, await confirmation before proceeding to next

---

## Proposal 1 — Finnhub Migration

Replace yfinance with Finnhub as primary data source across `ingest.py` and `signals.py`.

**Requirements:**
- All price, fundamentals, news, analyst recommendations, and earnings data fetched via Finnhub API
- Batch API calls to stay within free tier rate limit (60 calls/minute)
- Add fallback handler: if Finnhub fails mid-session, log the failure, send Telegram alert, and fall back to last cached data — do not crash the pipeline
- New API endpoint: `GET /api/portfolio/datasource` — shows current data provider status and timestamp of last successful fetch
- Verify all existing tickers return complete data before proceeding

**Test required:**
- Run Phase 1 dry-run with Finnhub and confirm all tickers return OHLCV + fundamentals + news with no missing fields
- Compare feature output before and after migration — flag any features that change by more than 5% in value
- Report Finnhub API call count per Phase 1 run to confirm free tier compliance

Do not proceed to Proposal 2 until Finnhub migration is confirmed clean.

---

## Proposal 2 — Russell 1000 Dynamic Screener

Add Phase 0 that runs every Sunday before retrain. Screens Russell 1000 and outputs `selected_tickers.json` with 40-50 tickers.

**Screening criteria (in order):**
1. Liquidity: average daily volume >1M shares
2. Fundamental score: composite of revenue growth, debt-to-assets, analyst revision momentum
3. Sector balance: ≤35% from any single sector
4. Correlation filter: no addition with >0.70 correlation to existing selections

**Requirements:**
- New module: `src/screener.py`
- Outputs `data/selected_tickers.json` — this replaces the hardcoded ticker list in `config.py`
- Existing tickers must survive the first screening pass — if any are dropped, flag it and await approval before removing them
- VPS memory audit required before first run — report peak memory usage during Phase 0 + Phase 1 combined. If it exceeds 2G, propose memory upgrade before proceeding
- New API endpoint: `GET /api/portfolio/universe` — returns current selected tickers, sector breakdown, and any changes from prior week
- Telegram weekly summary updated to include universe additions and removals

**Test required:**
- Run Phase 0 dry-run and report: tickers selected, sector distribution, any existing tickers dropped, peak memory usage
- Do not retrain on expanded universe until memory audit passes and you receive approval

---

## Proposal 3 — Investment Committee Filter

Add 3-agent deliberation layer between Phase 4 and Phase 5 using Claude API.

**Architecture:**
- **Bull Agent:** given ticker fundamentals, price action, VIX regime, last 3 days FinBERT sentiment — generate 3 strongest arguments FOR the trade
- **Bear Agent:** same inputs — generate 3 strongest arguments AGAINST the trade
- Bear and Bull agents run in parallel
- **Chair Agent:** receives both argument sets and original model signal — returns one verdict: PROCEED / SKIP / ESCALATE

**Execution rules:**
- PROCEED → Phase 5 executes normally
- SKIP → trade blocked, full reasoning logged to `data/committee_log.json`
- ESCALATE → trade blocked, Telegram alert sent with Bull/Bear/Chair summary for manual review

**Requirements:**
- New module: `src/committee.py`
- Inserted between Phase 4 (`signals.py`) and Phase 5 (`executor.py`)
- All three agents run via Claude API (`claude-sonnet-4-6`, max_tokens 500 per agent)
- Total latency must not exceed 15 seconds — if it does, log a timeout and default to PROCEED to avoid blocking execution
- Logs every verdict to `data/committee_log.json` with timestamp, ticker, signal, Bull args, Bear args, Chair verdict
- New API endpoint: `GET /api/portfolio/committee` — returns last 30 days of verdicts with Bull/Bear/Chair divergence stats

**Test required:**
- Run committee dry-run against last 5 signal files — report verdict distribution (PROCEED/SKIP/ESCALATE ratio) and average latency
- Confirm timeout fallback works correctly

---

## Proposal 4 — Earnings Calendar Awareness

Add earnings proximity as a feature and pre-trade risk check.

**Requirements:**
- New feature: `days_to_earnings` — trading days until next earnings report per ticker per day
- Finnhub earnings calendar API provides this data
- Pre-trade check in `signals.py`: if `days_to_earnings ≤ 5`, add `EARNINGS_NEAR` flag to signal output
- Committee agents receive `days_to_earnings` as part of their input context
- Hard block: no new position opens within 2 trading days of earnings — log blocked trades separately
- Dashboard signals panel updated to display `EARNINGS_NEAR` flag on affected tickers

**Test required:**
- Run Phase 4 dry-run and confirm `days_to_earnings` populates correctly for all tickers
- Verify hard block logic works — simulate a ticker with earnings in 1 trading day and confirm it is blocked

---

## Proposal 5 — Volatility-Adjusted Position Sizing

Replace fixed ~$97K position sizing with volatility-adjusted sizing in `executor.py`.

**Requirements:**
- Sizing formula: `position_size = base_allocation / (rolling_std_20 / mean_rolling_std_20)`
- Floor: $50K minimum per position
- Ceiling: $150K maximum per position
- `rolling_std_20` already exists as a feature — use it directly
- Position size logged per trade alongside signal probability and committee verdict
- Dashboard positions table updated to show allocated size vs default size

**Test required:**
- Run sizing calculation across all current tickers and report expected position sizes
- Confirm floor and ceiling constraints are enforced
- Dry-run Phase 5 with new sizing logic — do not execute real trades, report what would have been allocated

---

## Proposal 6 — FinBERT Reintegration Trigger

Add automated reintegration check to `train.py`.

**Requirements:**
- On every Sunday retrain, calculate sentiment coverage: non-zero sentiment rows / total training rows
- If coverage ≥ 30%, automatically unsuspend sentiment features (remove from `_SUSPENDED_FEATURES`)
- Send Telegram notification when reintegration triggers: include coverage percentage and which features were unsuspended
- If coverage < 30%, log current coverage to metrics and continue without change
- After Finnhub migration, sentiment accumulation rate will increase — monitor weekly

**Test required:**
- Confirm coverage calculation logic is correct
- Simulate a coverage threshold trigger in a dry-run environment and verify Telegram notification fires correctly

---

## Reporting Format After Each Proposal

After completing and testing each proposal, report in this format:

1. What was implemented (files changed, new modules added)
2. Test results (dry-run output, metrics, any anomalies)
3. Any deviations from the spec and why
4. Confirmation that the proposal is production-ready
5. Memory and latency impact if applicable

Await my approval after each report before proceeding to the next proposal.

---

## Final Note

This is a paper-to-real-money transition infrastructure upgrade. Do not rush. A clean implementation of each proposal is more important than speed. If anything in the spec is ambiguous or technically problematic, flag it before implementing — do not make assumptions.
