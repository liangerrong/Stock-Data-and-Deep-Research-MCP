# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install "mcp>=1.0.0" akshare yfinance pandas tabulate

# Optional free HK product/geography revenue adapter (requires logged-in Futu OpenD)
pip install futu-api

# Run all tests
python -m pytest tests/

# Run unit tests only
python -m pytest tests/unit/

# Run integration tests only
python -m pytest tests/integration/

# Run a single test file
python -m pytest tests/unit/test_akshare_client_financials.py

# Run a single test by name
python -m pytest tests/unit/test_akshare_client_financials.py::test_fetch_market_snapshot

# Start the MCP server manually (for debugging)
python -m src.server
```

## Architecture

This is an MCP (Model Context Protocol) server that wraps Akshare's A-share financial APIs for use by AI agents (Claude, Cursor, etc.).

The historical-package path is intentionally specialized for Anthropic's `claude-for-financial-services/equity-research` `initiating-coverage` plugin, especially its historical financial modeling prerequisites. It remains a data-preparation layer rather than a replacement for primary-filing verification.

**Entry point:** `src/server.py` — creates the MCP `Server` instance, registers three tools (`get_financials`, `search_stock`, `build_historical_financial_package`), and runs over stdio.

**Layer separation:**
- `src/tools/` — thin MCP tool handlers; catch all exceptions and return human-readable strings (never raise to the MCP layer)
- `src/core/akshare_client.py` — all Akshare API calls live here; raises `ValueError` for business-logic errors
- `src/core/yfinance_client.py` — HK quote metadata, financial currency, statements, and ticker search
- `src/core/futu_client.py` — optional free OpenD adapter for HK product/industry/geography/business revenue breakdowns
- `src/core/historical_package.py` — normalizes multi-source A-share history, runs quality checks, and writes the research package
- `src/core/hk_historical_package.py` — builds the HK package with yfinance as the only monetary-statement source
- `src/utils/file_utils.py` — DataFrame → Markdown/CSV serialization helpers

**Data flow for `get_financials`:**
1. `fetch_market_snapshot()` — calls `stock_profile_cninfo` (巨潮资讯) for name/shares, then `stock_zh_a_hist` for the latest closing price
2. `fetch_raw_sina_reports()` — calls `stock_financial_report_sina` exactly three times to pre-fetch raw data for all report types, minimizing API calls
3. `fetch_latest_quarterly_report()` — reuses the raw data, filters to non-annual reports (NOT ending in `1231`), takes only the latest quarter row, merges on `报告日`
4. `fetch_financial_history()` — reuses the raw data, filters to annual reports (`报告日` ending in `1231`), merges on `报告日`
5. All DataFrames are written into a single `{stock_code}_financial_data.md` file in order: Market Snapshot → Latest Quarterly Report → Annual Financial History; only the file path is returned to the AI

**Stock code lookup (`search_stock`):**
- **A 股 (`market="cn"`):** Full name→code mapping is fetched once via `stock_info_a_code_name()` and cached at `src/core/.stock_codes_cache.json`. Supports exact and partial name matching.
- **港股 (`market="hk"`):** Uses `yf.Search()` (yfinance Search API) to look up HK tickers on demand — no bulk download required. Results are incrementally cached at `src/core/.hk_stock_codes_cache.json`. Cache is checked first (exact then partial match); on miss, `yf.Search()` is called and the result is appended to the cache.
- **Important:** `market` defaults to `"cn"`. For HK stocks the caller **must** pass `market="hk"`; otherwise the search runs against A-share data and will fail silently.
- The old `_build_hk_cache()` approach (`ak.stock_hk_spot_em()`) was removed because it issues 46 paginated requests to 东方财富 and reliably times out.

**Output directory:** `get_financials` accepts an optional `output_dir`; falls back to `os.getcwd()` if the path is absent or invalid.

**Historical package (`build_historical_financial_package`):** Supports A shares and HK stocks. The HK path uses yfinance for all monetary statements and never fetches Eastmoney HK monetary statements or indicators. If the optional free Futu OpenD login is available, it adds issuer-disclosed product/industry/geography/business revenue; otherwise the segment files retain headers and the quality report records a warning. Normalized numeric tables retain original values/units and expose standardized values/units plus the conversion multiplier. Network failures in supplemental sources produce a partial package with warnings; missing primary statements remain a failed quality check.

## Testing approach

Unit tests mock all Akshare calls (`@patch("src.core.akshare_client.ak.*")`). Integration tests mock at the tool-handler boundary (`@patch("src.tools.get_financials.fetch_*")`). No test hits the real network. Use `tempfile.TemporaryDirectory` for file output in tests.

## MCP client configuration

```json
{
  "mcpServers": {
    "ashare-mcp": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "PYTHONPATH": "C:/absolute/path/to/this/repo"
      }
    }
  }
}
```

The server requires network access to the following endpoints at runtime:
- **新浪财经** — A-share financial statements (`get_financials`, A 股)
- **巨潮资讯** — A-share market snapshot (`get_financials`, A 股)
- **东方财富** — A-share price history (`get_financials`, A 股)
- **Yahoo Finance** — HK stock data and name search (`get_financials` + `search_stock`, 港股)
- **Futu OpenD (optional free login)** — HK issuer-disclosed product/geography revenue breakdowns
