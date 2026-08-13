"""Build an auditable Hong Kong equity historical financial package."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
from pathlib import Path
from typing import Callable

import pandas as pd

from src.core.akshare_client import (
    fetch_hk_company_profile,
    fetch_hk_dividend_history,
    fetch_hk_financial_indicators,
    fetch_hk_provider_reports,
    fetch_hk_report_metadata,
    fetch_hk_security_profile,
)
from src.core.yfinance_client import (
    create_ticker_obj,
    fetch_hk_market_snapshot,
    fetch_hk_raw_reports,
    fetch_hk_security_metadata,
)


STATEMENT_FILES = {
    "资产负债表": "balance_sheet.csv",
    "利润表": "income_statement.csv",
    "现金流量表": "cash_flow_statement.csv",
}
STATEMENT_METADATA = {"报告日", "数据源", "是否审计", "公告日期", "币种", "币种来源", "类型"}
PROVIDER_METADATA = {
    "SECUCODE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "ORG_CODE", "REPORT_DATE",
    "DATE_TYPE_CODE", "FISCAL_YEAR", "START_DATE", "STD_ITEM_CODE", "STD_REPORT_DATE",
}

HK_CORE_METRICS = [
    ("营业收入", "利润表", ["Total Revenue", "Operating Revenue"]),
    ("营业成本", "利润表", ["Cost Of Revenue", "Reconciled Cost Of Revenue"]),
    ("销售及管理费用", "利润表", ["Selling General And Administration"]),
    ("营业利润", "利润表", ["Operating Income"]),
    ("利润总额", "利润表", ["Pretax Income"]),
    ("所得税费用", "利润表", ["Tax Provision"]),
    ("净利润", "利润表", ["Net Income"]),
    ("归属于普通股股东的净利润", "利润表", ["Net Income Common Stockholders"]),
    ("基本每股收益", "利润表", ["Basic EPS"]),
    ("稀释每股收益", "利润表", ["Diluted EPS"]),
    ("现金及短期投资", "资产负债表", ["Cash Cash Equivalents And Short Term Investments"]),
    ("现金及现金等价物", "资产负债表", ["Cash And Cash Equivalents"]),
    ("应收账款", "资产负债表", ["Accounts Receivable"]),
    ("存货", "资产负债表", ["Inventory"]),
    ("固定资产净额", "资产负债表", ["Net PPE"]),
    ("资产总计", "资产负债表", ["Total Assets"]),
    ("负债合计", "资产负债表", ["Total Liabilities Net Minority Interest", "Total Liabilities"]),
    ("普通股股东权益", "资产负债表", ["Stockholders Equity"]),
    ("少数股东权益", "资产负债表", ["Minority Interest"]),
    ("所有者权益合计", "资产负债表", ["Total Equity Gross Minority Interest"]),
    ("期末普通股股数", "资产负债表", ["Ordinary Shares Number"]),
    ("经营活动产生的现金流量净额", "现金流量表", ["Operating Cash Flow"]),
    ("资本开支", "现金流量表", ["Capital Expenditure"]),
    ("现金变动", "现金流量表", ["Changes In Cash"]),
    ("汇率变动对现金的影响", "现金流量表", ["Effect Of Exchange Rate Changes"]),
    ("期初现金余额", "现金流量表", ["Beginning Cash Position"]),
    ("期末现金余额", "现金流量表", ["End Cash Position"]),
]
EPS_METRICS = {"基本每股收益", "稀释每股收益"}
SHARE_METRICS = {"期末普通股股数"}


def normalize_hk_ticker(value: str) -> tuple[str, str]:
    """Return (Yahoo ticker, five-digit Eastmoney code)."""
    text = str(value).strip().upper()
    raw = text[:-3] if text.endswith(".HK") else text
    if not raw.isdigit() or not 1 <= len(raw) <= 5:
        raise ValueError("HK stock code must be numeric with optional .HK suffix, e.g. 0700.HK or 00700")
    stripped = raw.lstrip("0") or "0"
    yahoo_code = stripped.zfill(4)
    return f"{yahoo_code}.HK", stripped.zfill(5)


def _period_key(value: object) -> str:
    return str(value).replace("-", "").replace("/", "")[:8]


def _numeric(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _currency(value: object) -> str:
    mapping = {"人民币": "CNY", "RMB": "CNY", "港元": "HKD", "港币": "HKD", "美元": "USD"}
    text = str(value).strip().upper()
    return mapping.get(text, text if text and text != "NAN" else "UNRESOLVED")


def _safe_fetch(name: str, function: Callable[[], pd.DataFrame], statuses: dict[str, dict]) -> pd.DataFrame:
    try:
        frame = function()
        if frame is None or frame.empty:
            statuses[name] = {"status": "empty", "rows": 0}
            return pd.DataFrame()
        statuses[name] = {"status": "ok", "rows": int(len(frame)), "columns": int(len(frame.columns))}
        return frame
    except Exception as exc:
        statuses[name] = {"status": "error", "rows": 0, "error": str(exc)}
        return pd.DataFrame()


def _safe_report_fetch(name: str, function: Callable[[], dict[str, pd.DataFrame]], statuses: dict[str, dict]) -> dict[str, pd.DataFrame]:
    try:
        reports = function()
        rows = sum(len(frame) for frame in reports.values() if frame is not None)
        statuses[name] = {"status": "ok" if rows else "empty", "rows": int(rows)}
        return reports
    except Exception as exc:
        statuses[name] = {"status": "error", "rows": 0, "error": str(exc)}
        return {name: pd.DataFrame() for name in STATEMENT_FILES}


def _select_annual_reports(reports: dict[str, pd.DataFrame], years: int) -> tuple[dict[str, pd.DataFrame], list[str]]:
    period_sets: list[set[str]] = []
    prepared: dict[str, pd.DataFrame] = {}
    for statement in STATEMENT_FILES:
        frame = reports.get(statement, pd.DataFrame()).copy()
        if frame.empty or "报告日" not in frame.columns:
            prepared[statement] = pd.DataFrame()
            period_sets.append(set())
            continue
        frame["报告日"] = frame["报告日"].map(_period_key)
        frame = frame[frame["报告日"].str.endswith("1231")]
        prepared[statement] = frame
        period_sets.append(set(frame["报告日"]))
    common = set.intersection(*period_sets) if period_sets and all(period_sets) else set()
    chosen = sorted(common, reverse=True)[:years]
    if not chosen:
        chosen = sorted(set().union(*period_sets), reverse=True)[:years]
    selected = {
        statement: frame[frame["报告日"].isin(chosen)].sort_values("报告日", ascending=False).reset_index(drop=True)
        if not frame.empty else frame
        for statement, frame in prepared.items()
    }
    return selected, sorted(chosen)


def _select_latest_interim(reports: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], list[str]]:
    candidates: dict[str, int] = {}
    prepared: dict[str, pd.DataFrame] = {}
    for statement in STATEMENT_FILES:
        frame = reports.get(statement, pd.DataFrame()).copy()
        if frame.empty or "报告日" not in frame.columns:
            prepared[statement] = pd.DataFrame()
            continue
        frame["报告日"] = frame["报告日"].map(_period_key)
        frame = frame[~frame["报告日"].str.endswith("1231")]
        prepared[statement] = frame
        for period in set(frame["报告日"]):
            candidates[period] = candidates.get(period, 0) + 1
    if not candidates:
        return {statement: pd.DataFrame() for statement in STATEMENT_FILES}, []
    best_period = sorted(candidates, key=lambda value: (candidates[value], value), reverse=True)[0]
    selected = {
        statement: frame[frame["报告日"] == best_period].head(1).reset_index(drop=True)
        if not frame.empty else frame
        for statement, frame in prepared.items()
    }
    return selected, [best_period]


def _statement_long(
    annual_reports: dict[str, pd.DataFrame],
    interim_reports: dict[str, pd.DataFrame],
    ticker: str,
) -> pd.DataFrame:
    rows: list[dict] = []
    url_paths = {"资产负债表": "balance-sheet", "利润表": "financials", "现金流量表": "cash-flow"}
    for report_period, reports in (("annual", annual_reports), ("latest_interim", interim_reports)):
        for statement, frame in reports.items():
            if frame.empty:
                continue
            for _, source_row in frame.iterrows():
                for label, value in source_row.items():
                    if label in STATEMENT_METADATA:
                        continue
                    number = _numeric(value)
                    if number is None:
                        continue
                    unit = "currency/share" if "EPS" in str(label) else ("shares" if "Shares Number" in str(label) else "currency")
                    rows.append({
                        "statement": statement,
                        "period": _period_key(source_row.get("报告日")),
                        "report_period": report_period,
                        "line_item": label,
                        "original_value": number,
                        "standardized_value": number,
                        "currency": _currency(source_row.get("币种")),
                        "currency_role": "issuer_financial_statement_currency",
                        "currency_basis": source_row.get("币种来源"),
                        "original_unit": unit,
                        "standard_unit": unit,
                        "scale_to_standard": 1.0,
                        "unit_basis": "Yahoo Finance statement field; no scale conversion",
                        "audited": source_row.get("是否审计"),
                        "announcement_date": source_row.get("公告日期"),
                        "consolidation_type": source_row.get("类型"),
                        "source_provider": "Yahoo Finance via yfinance",
                        "source_url": f"https://finance.yahoo.com/quote/{ticker}/{url_paths[statement]}/",
                    })
    return pd.DataFrame(rows)


def _lookup(reports: dict[str, pd.DataFrame], statement: str, period: str, labels: list[str]) -> float | None:
    frame = reports.get(statement, pd.DataFrame())
    if frame.empty:
        return None
    matching = frame[frame["报告日"].map(_period_key) == period]
    if matching.empty:
        return None
    row = matching.iloc[0]
    for label in labels:
        if label in row.index:
            number = _numeric(row[label])
            if number is not None:
                return number
    return None


def _build_core_actuals(annual_reports: dict[str, pd.DataFrame], periods: list[str], financial_currency: str) -> pd.DataFrame:
    rows: list[dict] = []
    for metric, statement, labels in HK_CORE_METRICS:
        unit = "currency/share" if metric in EPS_METRICS else ("shares" if metric in SHARE_METRICS else "currency")
        output = {
            "metric": metric,
            "source_statement": statement,
            "calculation": "reported",
            "currency": "N/A" if metric in SHARE_METRICS else financial_currency,
            "currency_role": "issuer_financial_statement_currency",
            "original_unit": unit,
            "standard_unit": unit,
            "scale_to_standard": 1.0,
            "unit_basis": "Yahoo Finance statement field",
        }
        for period in periods:
            value = _lookup(annual_reports, statement, period, labels)
            if metric == "资本开支" and value is not None:
                value = abs(value)
            output[f"{period[:4]}A"] = value
        rows.append(output)
    indexed = {row["metric"]: row for row in rows}
    for metric, formula in (("毛利", "营业收入 - 营业成本"), ("自由现金流", "经营现金流 - 资本开支")):
        output = {
            "metric": metric,
            "source_statement": "derived",
            "calculation": formula,
            "currency": financial_currency,
            "currency_role": "issuer_financial_statement_currency",
            "original_unit": "currency",
            "standard_unit": "currency",
            "scale_to_standard": 1.0,
            "unit_basis": "derived from same-currency statement fields",
        }
        for period in periods:
            column = f"{period[:4]}A"
            left_name, right_name = (("营业收入", "营业成本") if metric == "毛利" else ("经营活动产生的现金流量净额", "资本开支"))
            left, right = indexed[left_name].get(column), indexed[right_name].get(column)
            output[column] = None if left is None or right is None else round(left - right, 2)
        rows.append(output)
    return pd.DataFrame(rows)


def _provider_statements_long(
    reports: dict[str, pd.DataFrame],
    report_metadata: pd.DataFrame,
    indicators: pd.DataFrame,
) -> pd.DataFrame:
    issuer_map = {}
    if not report_metadata.empty:
        issuer_map = {
            _period_key(row.get("REPORT_DATE")): _currency(row.get("CURRENCY"))
            for _, row in report_metadata.iterrows()
        }
    provider_map = {}
    if not indicators.empty and "REPORT_DATE" in indicators.columns:
        provider_map = {
            _period_key(row.get("REPORT_DATE")): _currency(row.get("CURRENCY"))
            for _, row in indicators.iterrows()
        }
    rows: list[dict] = []
    for statement, frame in reports.items():
        if frame is None or frame.empty:
            continue
        for _, source_row in frame.iterrows():
            amount = _numeric(source_row.get("AMOUNT"))
            if amount is None:
                continue
            period = _period_key(source_row.get("REPORT_DATE"))
            issuer_currency = issuer_map.get(period, "UNRESOLVED")
            provider_currency = provider_map.get(period, "UNRESOLVED")
            rows.append({
                "statement": statement,
                "period": period,
                "line_item": source_row.get("STD_ITEM_NAME"),
                "original_value": amount,
                "currency": "UNRESOLVED",
                "issuer_reported_currency": issuer_currency,
                "provider_claimed_currency": provider_currency,
                "currency_status": "ambiguous_provider_transformation_do_not_model",
                "source_provider": "东方财富 via AkShare",
                "source_url": "https://emweb.securities.eastmoney.com/PC_HKF10/FinancialAnalysis/index",
            })
    return pd.DataFrame(rows)


def _indicators_long(indicators: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if indicators.empty:
        return pd.DataFrame()
    metadata = PROVIDER_METADATA | {"SECURITY_NAME_ABBR", "CURRENCY", "IS_CNY_CODE", "ACCOUNT_STANDARD", "REPORT_TYPE"}
    for _, source_row in indicators.iterrows():
        period = _period_key(source_row.get("REPORT_DATE") or source_row.get("STD_REPORT_DATE"))
        for metric, value in source_row.items():
            if metric in metadata:
                continue
            number = _numeric(value)
            if number is None:
                continue
            text = str(metric).upper()
            if any(token in text for token in ("RATIO", "RATE", "ROE", "ROA", "YOY", "QOQ")):
                unit, currency = "%", "N/A"
            elif any(token in text for token in ("SHARES", "CAPITAL")):
                unit, currency = "shares", "N/A"
            else:
                unit, currency = "provider_amount_or_per_share", "UNRESOLVED"
            rows.append({
                "period": period,
                "metric": metric,
                "original_value": number,
                "standardized_value": number,
                "currency": currency,
                "original_unit": unit,
                "standard_unit": unit,
                "scale_to_standard": 1.0,
                "unit_basis": "Eastmoney field; monetary currency transformation unresolved",
                "currency_status": "not_for_model" if currency == "UNRESOLVED" else "non_monetary",
                "source_provider": "东方财富 via AkShare",
            })
    return pd.DataFrame(rows)


def _dividends_long(dividends: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if dividends.empty:
        return pd.DataFrame()
    currency_map = {"港币": "HKD", "港元": "HKD", "美元": "USD", "人民币": "CNY"}
    for _, source_row in dividends.iterrows():
        scheme = str(source_row.get("分红方案", ""))
        declared = re.search(r"每股派(港币|港元|美元|人民币)([0-9.]+)元", scheme)
        if declared:
            rows.append({
                "period": source_row.get("财政年度"),
                "announcement_date": source_row.get("最新公告日期"),
                "distribution_type": source_row.get("分配类型"),
                "metric": "每股现金股息",
                "original_value": float(declared.group(2)),
                "standardized_value": float(declared.group(2)),
                "currency": currency_map[declared.group(1)],
                "original_unit": "currency/share",
                "standard_unit": "currency/share",
                "scale_to_standard": 1.0,
                "unit_basis": "parsed from Eastmoney dividend plan text",
                "source_text": scheme,
                "source_provider": "东方财富 via AkShare",
            })
        equivalent = re.search(r"相当于港币([0-9.]+)元", scheme)
        if equivalent:
            rows.append({
                "period": source_row.get("财政年度"),
                "announcement_date": source_row.get("最新公告日期"),
                "distribution_type": source_row.get("分配类型"),
                "metric": "每股现金股息_港币等值",
                "original_value": float(equivalent.group(1)),
                "standardized_value": float(equivalent.group(1)),
                "currency": "HKD",
                "original_unit": "currency/share",
                "standard_unit": "currency/share",
                "scale_to_standard": 1.0,
                "unit_basis": "provider-disclosed HKD equivalent; no independent FX recalculation",
                "source_text": scheme,
                "source_provider": "东方财富 via AkShare",
            })
    return pd.DataFrame(rows)


def _unit_dictionary(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    columns = ["currency", "original_unit", "standard_unit", "scale_to_standard", "unit_basis"]
    rows: list[pd.DataFrame] = []
    for dataset, frame in datasets.items():
        if frame.empty or not set(columns).issubset(frame.columns):
            continue
        metric_column = "metric" if "metric" in frame.columns else "line_item"
        current = frame[[metric_column, *columns]].rename(columns={metric_column: "metric"}).drop_duplicates()
        current.insert(0, "dataset", dataset)
        rows.append(current)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["dataset", "metric", *columns])


def _currency_manifest(identity: dict, report_metadata: pd.DataFrame, dividends_long: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "dataset": "market_snapshot",
            "currency_role": "quote_currency",
            "currency": identity["quote_currency"],
            "basis": "Yahoo Finance info.currency",
            "model_eligible": "yes_for_market_values",
        },
        {
            "dataset": "statements_long/core_actuals",
            "currency_role": "issuer_financial_statement_currency",
            "currency": identity["financial_currency"],
            "basis": "Yahoo Finance info.financialCurrency",
            "model_eligible": "yes_if_not_UNRESOLVED",
        },
        {
            "dataset": "provider_statements_long/financial_indicators_long",
            "currency_role": "provider_amount_currency",
            "currency": "UNRESOLVED",
            "basis": "Eastmoney report-list and indicator currency fields can conflict; line-item transformation is not documented",
            "model_eligible": "no",
        },
    ]
    if not report_metadata.empty and "CURRENCY" in report_metadata.columns:
        for value in sorted({_currency(value) for value in report_metadata["CURRENCY"].dropna()}):
            rows.append({
                "dataset": "hk_report_metadata",
                "currency_role": "issuer_report_list_label",
                "currency": value,
                "basis": "Eastmoney report list CURRENCY field",
                "model_eligible": "metadata_only",
            })
    if not dividends_long.empty:
        for value in sorted(set(dividends_long["currency"].dropna().astype(str))):
            rows.append({
                "dataset": "dividend_history_long",
                "currency_role": "declared_or_provider_equivalent_dividend_currency",
                "currency": value,
                "basis": "parsed from dividend plan text",
                "model_eligible": "yes_with_metric_label",
            })
    return pd.DataFrame(rows)


def _quality_checks(
    snapshot: dict,
    identity: dict,
    annual_reports: dict[str, pd.DataFrame],
    periods: list[str],
    requested_years: int,
    core_actuals: pd.DataFrame,
    statements_long: pd.DataFrame,
    provider_statements: pd.DataFrame,
    statuses: dict[str, dict],
) -> tuple[list[dict], str]:
    checks: list[dict] = []
    add = lambda name, status, detail: checks.append({"check": name, "status": status, "detail": detail})
    missing = [name for name, frame in annual_reports.items() if frame.empty]
    add("annual_statements", "FAIL" if missing else "PASS", f"missing: {', '.join(missing)}" if missing else "all three statements available")
    coverage_status = "PASS" if len(periods) >= requested_years else ("WARN" if len(periods) >= 3 else "FAIL")
    add("annual_period_coverage", coverage_status, f"{len(periods)} common annual periods; requested {requested_years}; minimum 3")
    price = _numeric(snapshot.get("current_price")) or 0
    shares = _numeric(snapshot.get("shares_outstanding")) or 0
    add("market_snapshot", "PASS" if price and shares else "WARN", "price and shares outstanding are non-zero" if price and shares else "zero/missing price or shares; do not use for valuation")
    financial_currency = identity.get("financial_currency")
    quote_currency = identity.get("quote_currency")
    currency_ok = financial_currency not in (None, "", "UNRESOLVED") and quote_currency not in (None, "", "UNRESOLVED")
    add("currency_metadata", "PASS" if currency_ok else "FAIL", f"quote={quote_currency}; financial={financial_currency}")
    statement_currencies = set(statements_long.get("currency", pd.Series(dtype=str)).dropna().astype(str))
    add("canonical_currency_consistency", "PASS" if statement_currencies == {financial_currency} else "FAIL", f"canonical statement currencies={sorted(statement_currencies)}")
    add("provider_currency_semantics", "WARN" if not provider_statements.empty else "PASS", "Eastmoney amounts retained as UNRESOLVED and excluded from modeling" if not provider_statements.empty else "no ambiguous provider amount data included")

    balance = annual_reports.get("资产负债表", pd.DataFrame())
    for _, row in balance.iterrows():
        period = _period_key(row.get("报告日"))
        assets = _numeric(row.get("Total Assets"))
        liabilities = _numeric(row.get("Total Liabilities Net Minority Interest"))
        equity = _numeric(row.get("Total Equity Gross Minority Interest"))
        if None in (assets, liabilities, equity):
            add(f"balance_sheet_{period}", "WARN", "assets/liabilities/equity fields missing")
        else:
            difference = assets - liabilities - equity
            tolerance = max(1.0, abs(assets) * 1e-6)
            add(f"balance_sheet_{period}", "PASS" if abs(difference) <= tolerance else "FAIL", f"difference={difference:.2f}; tolerance={tolerance:.2f}")

    year_columns = [column for column in core_actuals.columns if column.endswith("A")]
    required = ["营业收入", "净利润", "资产总计", "负债合计", "经营活动产生的现金流量净额", "资本开支"]
    indexed = core_actuals.set_index("metric")
    missing_cells = [f"{metric}:{year}" for metric in required for year in year_columns if metric not in indexed.index or pd.isna(indexed.at[metric, year])]
    add("core_actuals_coverage", "WARN" if missing_cells else "PASS", f"missing {len(missing_cells)} required cells" if missing_cells else "required core metrics populated")
    add("segment_coverage", "WARN", "mechanical HK product/geography source unavailable; extract from issuer filings")
    add("official_report_links", "WARN", "HKEX filing search entry included, but report-specific official links were not mechanically resolved")
    failed = [name for name, status in statuses.items() if status["status"] == "error"]
    add("supplemental_sources", "WARN" if failed else "PASS", f"failed: {', '.join(failed)}" if failed else "all requested supplemental sources responded")
    grade = "FAIL" if any(check["status"] == "FAIL" for check in checks) else ("WARN" if any(check["status"] == "WARN" for check in checks) else "PASS")
    return checks, grade


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def build_hk_historical_financial_package(
    stock_code: str,
    years: int,
    output_dir: str,
    include_latest_interim: bool = True,
) -> dict:
    ticker, em_code = normalize_hk_ticker(stock_code)
    generated_at = dt.datetime.now().astimezone()
    stamp = generated_at.strftime("%Y%m%dT%H%M%S%f")
    package_dir = Path(output_dir).expanduser().resolve() / f"{ticker.replace('.', '_')}_historical_financial_package_{stamp}"
    package_dir.mkdir(parents=True, exist_ok=False)

    ticker_obj = create_ticker_obj(ticker)
    identity = fetch_hk_security_metadata(ticker, ticker_obj)
    identity["eastmoney_code"] = em_code
    snapshot = fetch_hk_market_snapshot(ticker, ticker_obj)
    statuses: dict[str, dict] = {}
    annual_raw = _safe_report_fetch("yahoo_annual_statements", lambda: fetch_hk_raw_reports(ticker, False, ticker_obj), statuses)
    interim_raw = _safe_report_fetch("yahoo_interim_statements", lambda: fetch_hk_raw_reports(ticker, True, ticker_obj), statuses) if include_latest_interim else {name: pd.DataFrame() for name in STATEMENT_FILES}
    annual_reports, annual_periods = _select_annual_reports(annual_raw, years)
    interim_reports, interim_periods = _select_latest_interim(interim_raw)

    report_metadata = _safe_fetch("eastmoney_report_metadata", lambda: fetch_hk_report_metadata(em_code), statuses)
    company_profile = _safe_fetch("company_profile", lambda: fetch_hk_company_profile(em_code), statuses)
    security_profile = _safe_fetch("security_profile", lambda: fetch_hk_security_profile(em_code), statuses)
    indicators_raw = _safe_fetch("financial_indicators", lambda: fetch_hk_financial_indicators(em_code), statuses)
    dividends = _safe_fetch("dividend_history", lambda: fetch_hk_dividend_history(em_code), statuses)
    provider_reports = _safe_report_fetch("eastmoney_provider_statements", lambda: fetch_hk_provider_reports(em_code), statuses)

    profile = pd.concat(
        [company_profile.reset_index(drop=True), security_profile.add_prefix("证券_").reset_index(drop=True)],
        axis=1,
    )
    statements_long = _statement_long(annual_reports, interim_reports, ticker)
    core_actuals = _build_core_actuals(annual_reports, annual_periods, identity["financial_currency"])
    provider_long = _provider_statements_long(provider_reports, report_metadata, indicators_raw)
    indicators_long = _indicators_long(indicators_raw)
    dividends_long = _dividends_long(dividends)
    empty_segments = pd.DataFrame(columns=["period", "classification", "segment", "metric", "original_value", "standardized_value", "currency", "original_unit", "standard_unit", "scale_to_standard", "unit_basis", "source_provider"])
    empty_shares = pd.DataFrame(columns=["change_date", "metric", "original_value", "standardized_value", "currency", "original_unit", "standard_unit", "scale_to_standard", "unit_basis", "source_provider"])
    unit_dictionary = _unit_dictionary({
        "statements_long": statements_long,
        "core_actuals": core_actuals,
        "financial_indicators_long": indicators_long,
        "dividend_history_long": dividends_long,
    })
    currency_manifest = _currency_manifest(identity, report_metadata, dividends_long)

    source_manifest = report_metadata.copy()
    if not source_manifest.empty:
        source_manifest["source_type"] = "Eastmoney report metadata; not an official filing link"
    hkex_entry = pd.DataFrame([{
        "SECUCODE": ticker,
        "SECURITY_CODE": em_code,
        "source_provider": "香港交易所披露易",
        "source_url": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh",
        "source_type": "official filing search entry; report-specific link unresolved",
    }])
    source_manifest = pd.concat([source_manifest, hkex_entry], ignore_index=True, sort=False)

    files: dict[str, str] = {}
    _write_csv(pd.DataFrame([snapshot]), package_dir / "market_snapshot.csv")
    files["market_snapshot"] = "market_snapshot.csv"
    (package_dir / "market_identity.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    files["market_identity"] = "market_identity.json"
    for statement, filename in STATEMENT_FILES.items():
        annual = annual_reports.get(statement, pd.DataFrame())
        interim = interim_reports.get(statement, pd.DataFrame())
        combined = pd.concat([annual, interim], ignore_index=True, sort=False) if not interim.empty else annual
        _write_csv(combined, package_dir / filename)
        files[statement] = filename
    datasets = {
        "statements_long": (statements_long, "statements_long.csv"),
        "provider_statements_long": (provider_long, "provider_statements_long.csv"),
        "core_actuals": (core_actuals, "core_actuals.csv"),
        "company_profile": (profile, "company_profile.csv"),
        "business_composition": (empty_segments, "business_composition.csv"),
        "business_composition_long": (empty_segments, "business_composition_long.csv"),
        "financial_abstract": (pd.DataFrame(), "financial_abstract_long.csv"),
        "financial_indicators": (indicators_long, "financial_indicators_long.csv"),
        "share_changes": (empty_shares, "share_changes.csv"),
        "share_changes_long": (empty_shares, "share_changes_long.csv"),
        "dividend_history": (dividends, "dividend_history.csv"),
        "dividend_history_long": (dividends_long, "dividend_history_long.csv"),
        "unit_dictionary": (unit_dictionary, "unit_dictionary.csv"),
        "currency_manifest": (currency_manifest, "currency_manifest.csv"),
        "source_manifest": (source_manifest, "source_manifest.csv"),
        "hk_report_metadata": (report_metadata, "hk_report_metadata.csv"),
    }
    for name, (frame, filename) in datasets.items():
        _write_csv(frame, package_dir / filename)
        files[name] = filename

    checks, grade = _quality_checks(
        snapshot, identity, annual_reports, annual_periods, years, core_actuals,
        statements_long, provider_long, statuses,
    )
    quality_lines = [
        f"# {ticker} 历史财务数据包质量报告", "",
        f"- 生成时间：{generated_at.isoformat()}",
        f"- 交易币种：{identity['quote_currency']}",
        f"- 财报币种：{identity['financial_currency']}",
        f"- 覆盖年度：{', '.join(period[:4] for period in annual_periods) or 'N/A'}",
        f"- 总体状态：**{grade}**", "", "## 自动检查", "",
        "| 检查项 | 状态 | 说明 |", "|---|---|---|",
    ]
    quality_lines.extend(f"| {check['check']} | {check['status']} | {check['detail']} |" for check in checks)
    quality_lines.extend([
        "", "## 使用边界", "",
        "- Yahoo Finance 三表按同一证券的 `info.financialCurrency` 标记；它与港股交易币种 HKD 是两个概念。",
        "- 东方财富报告列表的发行人币种标签与主要指标/金额展示口径可能冲突，相关金额全部标为 UNRESOLVED，不得进入模型。",
        "- 港股分部数据及报告级 HKEX 官方链接仍需从发行人年报或披露易补充。",
        "- sharesOutstanding 不等同于经核验的自由流通股本；行情、股数为 0 时不得用于估值。",
        "- 本包是机械底稿，不替代发行人定期报告、会计政策及追溯重述核验。",
    ])
    (package_dir / "quality_report.md").write_text("\n".join(quality_lines), encoding="utf-8")
    files["quality_report"] = "quality_report.md"

    manifest = {
        "schema_version": "2.0.0",
        "stock_code": ticker,
        "market": "HK",
        "generated_at": generated_at.isoformat(),
        "requested_years": years,
        "annual_periods": annual_periods,
        "latest_interim_periods": interim_periods,
        "quote_currency": identity["quote_currency"],
        "financial_currency": identity["financial_currency"],
        "quality_grade": grade,
        "files": files,
        "source_statuses": statuses,
        "checks": checks,
        "source_policy": {
            "canonical_statements": "Yahoo Finance via yfinance; currency inherited explicitly from info.financialCurrency",
            "provider_cross_check": "Eastmoney via AkShare; monetary currency unresolved and excluded from modeling",
            "profile_dividends": "Eastmoney via AkShare",
            "official_links": "HKEXnews search entry only; resolve report-specific links before audit use",
            "market_data": "Yahoo Finance; zero means unavailable",
        },
    }
    files["manifest"] = "manifest.json"
    (package_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_path = shutil.make_archive(str(package_dir), "zip", root_dir=package_dir)
    return {
        "status": "success",
        "stock_code": ticker,
        "market": "HK",
        "quote_currency": identity["quote_currency"],
        "financial_currency": identity["financial_currency"],
        "quality_grade": grade,
        "annual_periods": annual_periods,
        "latest_interim_periods": interim_periods,
        "package_dir": os.path.abspath(package_dir),
        "manifest": os.path.abspath(package_dir / "manifest.json"),
        "quality_report": os.path.abspath(package_dir / "quality_report.md"),
        "archive": os.path.abspath(archive_path),
    }
