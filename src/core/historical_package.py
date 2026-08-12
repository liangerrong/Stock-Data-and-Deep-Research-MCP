"""Build an auditable A-share historical financial research package."""

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
    fetch_company_profile,
    fetch_disclosure_reports,
    fetch_dividend_history,
    fetch_financial_abstract,
    fetch_financial_indicators,
    fetch_main_business_composition,
    fetch_market_snapshot,
    fetch_raw_sina_reports,
    fetch_share_changes,
)


STATEMENT_FILES = {
    "资产负债表": "balance_sheet.csv",
    "利润表": "income_statement.csv",
    "现金流量表": "cash_flow_statement.csv",
}

STATEMENT_METADATA = {
    "报告日",
    "数据源",
    "是否审计",
    "公告日期",
    "币种",
    "类型",
    "更新日期",
}

CORE_METRICS = [
    ("营业收入", "利润表", ["营业收入", "营业总收入"]),
    ("营业成本", "利润表", ["营业成本", "营业总成本"]),
    ("销售费用", "利润表", ["销售费用"]),
    ("管理费用", "利润表", ["管理费用"]),
    ("研发费用", "利润表", ["研发费用"]),
    ("财务费用", "利润表", ["财务费用"]),
    ("营业利润", "利润表", ["营业利润"]),
    ("利润总额", "利润表", ["利润总额"]),
    ("所得税费用", "利润表", ["所得税费用"]),
    ("净利润", "利润表", ["净利润"]),
    ("归属于母公司所有者的净利润", "利润表", ["归属于母公司所有者的净利润"]),
    ("基本每股收益", "利润表", ["基本每股收益"]),
    ("稀释每股收益", "利润表", ["稀释每股收益"]),
    ("货币资金", "资产负债表", ["货币资金"]),
    ("应收账款", "资产负债表", ["应收账款"]),
    ("存货", "资产负债表", ["存货"]),
    ("固定资产净额", "资产负债表", ["固定资产净额", "固定资产净值"]),
    ("资产总计", "资产负债表", ["资产总计"]),
    ("负债合计", "资产负债表", ["负债合计"]),
    ("实收资本(或股本)", "资产负债表", ["实收资本(或股本)"]),
    ("归属于母公司股东权益合计", "资产负债表", ["归属于母公司股东权益合计"]),
    ("少数股东权益", "资产负债表", ["少数股东权益"]),
    ("所有者权益合计", "资产负债表", ["所有者权益(或股东权益)合计"]),
    ("经营活动产生的现金流量净额", "现金流量表", ["经营活动产生的现金流量净额"]),
    (
        "资本开支",
        "现金流量表",
        ["购建固定资产、无形资产和其他长期资产所支付的现金"],
    ),
    ("现金及现金等价物净增加额", "现金流量表", ["现金及现金等价物净增加额"]),
    ("期初现金及现金等价物余额", "现金流量表", ["期初现金及现金等价物余额"]),
    ("期末现金及现金等价物余额", "现金流量表", ["期末现金及现金等价物余额"]),
]

EPS_METRICS = {"基本每股收益", "稀释每股收益"}
SEGMENT_UNIT_MAP = {
    "主营收入": ("元", "元", 1.0),
    "主营成本": ("元", "元", 1.0),
    "主营利润": ("元", "元", 1.0),
    "收入比例": ("比例(0-1)", "%", 100.0),
    "成本比例": ("比例(0-1)", "%", 100.0),
    "利润比例": ("比例(0-1)", "%", 100.0),
    "毛利率": ("比例(0-1)", "%", 100.0),
}
DIVIDEND_UNIT_MAP = {
    "送转股份-送转总比例": ("股/10股", "股/10股", 1.0),
    "送转股份-送股比例": ("股/10股", "股/10股", 1.0),
    "送转股份-转股比例": ("股/10股", "股/10股", 1.0),
    "现金分红-现金分红比例": ("元/10股", "元/10股", 1.0),
    "现金分红-股息率": ("%", "%", 1.0),
    "每股收益": ("元/股", "元/股", 1.0),
    "每股净资产": ("元/股", "元/股", 1.0),
    "每股公积金": ("元/股", "元/股", 1.0),
    "每股未分配利润": ("元/股", "元/股", 1.0),
    "净利润同比增长": ("%", "%", 1.0),
    "总股本": ("股", "股", 1.0),
}


def _period_key(value: object) -> str:
    text = str(value).replace("-", "").replace("/", "")
    return text[:8]


def _numeric(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _normalize_currency(value: object) -> str:
    text = str(value).strip().upper()
    if text in {"人民币", "RMB", "CNY", "元"} or not text or text == "NAN":
        return "CNY"
    return text


def _infer_metric_unit(metric: object, default: str = "N/A") -> tuple[str, str, float, str]:
    """Return original unit, standard unit, multiplier, and inference basis."""
    text = str(metric).strip()
    parenthetical = re.findall(r"[（(]([^）)]+)[）)]", text)
    if parenthetical:
        token = parenthetical[-1].strip()
        explicit = {
            "元": "元",
            "%": "%",
            "次": "次",
            "天": "天",
            "股": "股",
        }.get(token)
        if explicit:
            unit = "元/股" if explicit == "元" and "每股" in text else explicit
            return unit, unit, 1.0, "字段名显式单位"
    if "每股" in text:
        return "元/股", "元/股", 1.0, "字段语义推断"
    if "周转天数" in text:
        return "天", "天", 1.0, "字段语义推断"
    if "周转率" in text:
        return "次", "次", 1.0, "字段语义推断"
    if "倍数" in text or text.endswith("倍"):
        return "倍", "倍", 1.0, "字段语义推断"
    if any(token in text for token in ("率", "比重", "比例", "增长")):
        return "%", "%", 1.0, "字段语义推断"
    if text == "总股本":
        return "股", "股", 1.0, "接口字段定义"
    return default, default, 1.0, "未确认"


def _annual_frame(df: pd.DataFrame | None, years: int) -> pd.DataFrame:
    if df is None or df.empty or "报告日" not in df.columns:
        return pd.DataFrame()
    result = df.copy()
    result["报告日"] = result["报告日"].map(_period_key)
    result = result[result["报告日"].str.endswith("1231")]
    return result.sort_values("报告日", ascending=False).head(years).reset_index(drop=True)


def _latest_interim_frame(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty or "报告日" not in df.columns:
        return pd.DataFrame()
    result = df.copy()
    result["报告日"] = result["报告日"].map(_period_key)
    result = result[~result["报告日"].str.endswith("1231")]
    return result.sort_values("报告日", ascending=False).head(1).reset_index(drop=True)


def _statement_long(
    annual_reports: dict[str, pd.DataFrame],
    interim_reports: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict] = []
    source_template = (
        "https://vip.stock.finance.sina.com.cn/corp/go.php/"
        "vFD_FinanceSummary/stockid/{stock_code}/displaytype/4.phtml"
    )
    for report_period, frames in (("annual", annual_reports), ("latest_interim", interim_reports)):
        for statement, df in frames.items():
            if df.empty:
                continue
            for _, source_row in df.iterrows():
                period = _period_key(source_row.get("报告日"))
                for label, value in source_row.items():
                    if label in STATEMENT_METADATA:
                        continue
                    number = _numeric(value)
                    if number is None:
                        continue
                    rows.append(
                        {
                            "statement": statement,
                            "period": period,
                            "report_period": report_period,
                            "line_item": label,
                            "original_value": number,
                            "standardized_value": number,
                            "currency": _normalize_currency(source_row.get("币种", "CNY")),
                            "original_unit": "元",
                            "standard_unit": "元",
                            "scale_to_standard": 1.0,
                            "unit_basis": "新浪财务报表接口金额单位",
                            "audited": source_row.get("是否审计"),
                            "announcement_date": source_row.get("公告日期"),
                            "consolidation_type": source_row.get("类型"),
                            "source_provider": "新浪财经",
                            "source_url_template": source_template,
                        }
                    )
    return pd.DataFrame(rows)


def _lookup(
    reports: dict[str, pd.DataFrame],
    statement: str,
    period: str,
    labels: list[str],
) -> float | None:
    df = reports.get(statement, pd.DataFrame())
    if df.empty:
        return None
    matching = df[df["报告日"].map(_period_key) == period]
    if matching.empty:
        return None
    row = matching.iloc[0]
    for label in labels:
        if label in row.index:
            value = _numeric(row[label])
            if value is not None:
                return value
    return None


def _build_core_actuals(annual_reports: dict[str, pd.DataFrame]) -> pd.DataFrame:
    periods = sorted(
        {
            _period_key(period)
            for df in annual_reports.values()
            if not df.empty
            for period in df["报告日"].tolist()
        }
    )
    rows: list[dict] = []
    for metric, statement, labels in CORE_METRICS:
        output = {
            "metric": metric,
            "source_statement": statement,
            "calculation": "reported",
            "currency": "CNY",
            "original_unit": "元/股" if metric in EPS_METRICS else "元",
            "standard_unit": "元/股" if metric in EPS_METRICS else "元",
            "scale_to_standard": 1.0,
            "unit_basis": "财务报表字段口径",
        }
        for period in periods:
            output[f"{period[:4]}A"] = _lookup(annual_reports, statement, period, labels)
        rows.append(output)

    derived_specs = [
        ("毛利", "营业收入 - 营业成本"),
        ("自由现金流", "经营活动产生的现金流量净额 - 资本开支"),
    ]
    indexed = {row["metric"]: row for row in rows}
    for metric, formula in derived_specs:
        output = {
            "metric": metric,
            "source_statement": "derived",
            "calculation": formula,
            "currency": "CNY",
            "original_unit": "元",
            "standard_unit": "元",
            "scale_to_standard": 1.0,
            "unit_basis": "派生自同单位报表字段",
        }
        for period in periods:
            column = f"{period[:4]}A"
            if metric == "毛利":
                left = indexed["营业收入"].get(column)
                right = indexed["营业成本"].get(column)
            else:
                left = indexed["经营活动产生的现金流量净额"].get(column)
                right = indexed["资本开支"].get(column)
            output[column] = None if left is None or right is None else round(left - right, 2)
        rows.append(output)
    return pd.DataFrame(rows)


def _abstract_long(df: pd.DataFrame, allowed_periods: set[str]) -> pd.DataFrame:
    if df.empty or not {"选项", "指标"}.issubset(df.columns):
        return pd.DataFrame()
    rows: list[dict] = []
    period_columns = [column for column in df.columns if _period_key(column) in allowed_periods]
    for _, source_row in df.iterrows():
        for column in period_columns:
            value = _numeric(source_row[column])
            if value is not None:
                original_unit, standard_unit, scale, basis = _infer_metric_unit(source_row["指标"], "元")
                rows.append(
                    {
                        "category": source_row["选项"],
                        "metric": source_row["指标"],
                        "period": _period_key(column),
                        "original_value": value,
                        "standardized_value": value * scale,
                        "currency": "CNY" if "元" in standard_unit else "N/A",
                        "original_unit": original_unit,
                        "standard_unit": standard_unit,
                        "scale_to_standard": scale,
                        "unit_basis": basis if basis != "未确认" else "财务摘要金额默认单位",
                        "source_provider": "新浪财经",
                    }
                )
    return pd.DataFrame(rows)


def _indicators_long(df: pd.DataFrame, allowed_periods: set[str]) -> pd.DataFrame:
    if df.empty or "日期" not in df.columns:
        return pd.DataFrame()
    rows: list[dict] = []
    for _, source_row in df.iterrows():
        period = _period_key(source_row["日期"])
        if period not in allowed_periods:
            continue
        for metric, value in source_row.items():
            if metric == "日期":
                continue
            number = _numeric(value)
            if number is not None:
                original_unit, standard_unit, scale, basis = _infer_metric_unit(metric)
                rows.append(
                    {
                        "period": period,
                        "metric": metric,
                        "original_value": number,
                        "standardized_value": number * scale,
                        "currency": "CNY" if "元" in standard_unit else "N/A",
                        "original_unit": original_unit,
                        "standard_unit": standard_unit,
                        "scale_to_standard": scale,
                        "unit_basis": basis,
                        "source_provider": "新浪财经",
                    }
                )
    return pd.DataFrame(rows)


def _filter_segments(df: pd.DataFrame, start_year: int) -> pd.DataFrame:
    if df.empty or "报告日期" not in df.columns:
        return pd.DataFrame()
    result = df.copy()
    result["报告日期"] = pd.to_datetime(result["报告日期"], errors="coerce")
    result = result[result["报告日期"].dt.year >= start_year]
    result["source_provider"] = "东方财富"
    result["source_url"] = "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/Index"
    return result.sort_values(["报告日期", "分类类型", "主营构成"], ascending=[False, True, True])


def _segments_long(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if df.empty:
        return pd.DataFrame()
    for _, source_row in df.iterrows():
        for metric, (original_unit, standard_unit, scale) in SEGMENT_UNIT_MAP.items():
            number = _numeric(source_row.get(metric))
            if number is None:
                continue
            rows.append(
                {
                    "stock_code": source_row.get("股票代码"),
                    "period": _period_key(source_row.get("报告日期")),
                    "classification": source_row.get("分类类型"),
                    "segment": source_row.get("主营构成"),
                    "metric": metric,
                    "original_value": number,
                    "standardized_value": number * scale,
                    "currency": "CNY" if standard_unit == "元" else "N/A",
                    "original_unit": original_unit,
                    "standard_unit": standard_unit,
                    "scale_to_standard": scale,
                    "unit_basis": "东方财富主营构成接口字段定义",
                    "source_provider": "东方财富",
                }
            )
    return pd.DataFrame(rows)


def _share_changes_long(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if df.empty:
        return pd.DataFrame()
    metadata = {"证券简称", "机构名称", "变动原因", "公告日期", "证券代码", "变动日期", "变动原因编码"}
    for _, source_row in df.iterrows():
        for metric, value in source_row.items():
            if metric in metadata:
                continue
            number = _numeric(value)
            if number is None:
                continue
            rows.append(
                {
                    "stock_code": source_row.get("证券代码"),
                    "change_date": source_row.get("变动日期"),
                    "announcement_date": source_row.get("公告日期"),
                    "change_reason": source_row.get("变动原因"),
                    "metric": metric,
                    "original_value": number,
                    "standardized_value": number * 10_000.0,
                    "currency": "N/A",
                    "original_unit": "万股",
                    "standard_unit": "股",
                    "scale_to_standard": 10_000.0,
                    "unit_basis": "巨潮股本变动接口单位",
                    "source_provider": "巨潮资讯",
                }
            )
    return pd.DataFrame(rows)


def _dividends_long(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if df.empty:
        return pd.DataFrame()
    for _, source_row in df.iterrows():
        for metric, (original_unit, standard_unit, scale) in DIVIDEND_UNIT_MAP.items():
            number = _numeric(source_row.get(metric))
            if number is None:
                continue
            rows.append(
                {
                    "period": source_row.get("报告期"),
                    "metric": metric,
                    "original_value": number,
                    "standardized_value": number * scale,
                    "currency": "CNY" if "元" in standard_unit else "N/A",
                    "original_unit": original_unit,
                    "standard_unit": standard_unit,
                    "scale_to_standard": scale,
                    "unit_basis": "东方财富分红接口字段定义",
                    "source_provider": "东方财富",
                }
            )
    return pd.DataFrame(rows)


def _unit_dictionary(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    unit_columns = ["metric", "currency", "original_unit", "standard_unit", "scale_to_standard", "unit_basis"]
    for dataset, df in datasets.items():
        current_source = df.rename(columns={"line_item": "metric"}) if "metric" not in df.columns else df
        if current_source.empty or not set(unit_columns).issubset(current_source.columns):
            continue
        current = current_source[unit_columns].drop_duplicates().copy()
        current.insert(0, "dataset", dataset)
        rows.append(current)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["dataset", *unit_columns])


def _safe_fetch(
    name: str,
    function: Callable[[], pd.DataFrame],
    statuses: dict[str, dict],
) -> pd.DataFrame:
    try:
        df = function()
        if df is None or df.empty:
            statuses[name] = {"status": "empty", "rows": 0}
            return pd.DataFrame()
        statuses[name] = {"status": "ok", "rows": int(len(df)), "columns": int(len(df.columns))}
        return df
    except Exception as exc:  # partial packages are more useful than total failure
        statuses[name] = {"status": "error", "rows": 0, "error": str(exc)}
        return pd.DataFrame()


def _quality_checks(
    snapshot: dict,
    annual_reports: dict[str, pd.DataFrame],
    core_actuals: pd.DataFrame,
    segments: pd.DataFrame,
    abstract: pd.DataFrame,
    unit_dictionary: pd.DataFrame,
    disclosures: pd.DataFrame,
    source_statuses: dict[str, dict],
) -> tuple[list[dict], str]:
    checks: list[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    missing_statements = [name for name, df in annual_reports.items() if df.empty]
    add(
        "annual_statements",
        "FAIL" if missing_statements else "PASS",
        "missing: " + ", ".join(missing_statements) if missing_statements else "all three statements available",
    )

    if snapshot.get("current_price", 0) and snapshot.get("circulating_shares", 0):
        add("market_snapshot", "PASS", "price and circulating shares are non-zero")
    else:
        add("market_snapshot", "WARN", "zero/missing price or circulating shares; do not use for valuation")

    balance = annual_reports.get("资产负债表", pd.DataFrame())
    if not balance.empty:
        for _, row in balance.iterrows():
            period = _period_key(row["报告日"])
            assets = _numeric(row.get("资产总计"))
            liabilities_equity = _numeric(row.get("负债和所有者权益(或股东权益)总计"))
            if assets is None or liabilities_equity is None:
                add(f"balance_sheet_{period}", "WARN", "required totals missing")
                continue
            difference = assets - liabilities_equity
            tolerance = max(1.0, abs(assets) * 1e-6)
            add(
                f"balance_sheet_{period}",
                "PASS" if abs(difference) <= tolerance else "FAIL",
                f"difference={difference:.2f}; tolerance={tolerance:.2f}",
            )

    cash_flow = annual_reports.get("现金流量表", pd.DataFrame())
    if not cash_flow.empty:
        for _, row in cash_flow.iterrows():
            period = _period_key(row["报告日"])
            opening = _numeric(row.get("期初现金及现金等价物余额"))
            change = _numeric(row.get("现金及现金等价物净增加额"))
            ending = _numeric(row.get("期末现金及现金等价物余额"))
            if opening is None or change is None or ending is None:
                add(f"cash_rollforward_{period}", "WARN", "opening/change/ending cash missing")
                continue
            difference = opening + change - ending
            tolerance = max(1.0, abs(ending) * 1e-6)
            add(
                f"cash_rollforward_{period}",
                "PASS" if abs(difference) <= tolerance else "FAIL",
                f"difference={difference:.2f}; tolerance={tolerance:.2f}",
            )

    year_columns = [column for column in core_actuals.columns if column.endswith("A")]
    required_metrics = ["营业收入", "净利润", "资产总计", "负债合计", "经营活动产生的现金流量净额", "资本开支"]
    core = core_actuals.set_index("metric")
    missing_cells = [
        f"{metric}:{year}"
        for metric in required_metrics
        for year in year_columns
        if metric not in core.index or pd.isna(core.at[metric, year])
    ]
    add(
        "core_actuals_coverage",
        "WARN" if missing_cells else "PASS",
        f"missing {len(missing_cells)} required cells" if missing_cells else "required core metrics populated",
    )

    reconciliation_specs = {
        "营业收入": ["营业总收入", "营业收入"],
        "净利润": ["净利润", "归属净利润", "归属于母公司所有者的净利润"],
    }
    if abstract.empty:
        add("cross_source_reconciliation", "WARN", "financial abstract unavailable")
    else:
        compared = 0
        mismatches: list[str] = []
        for metric, candidates in reconciliation_specs.items():
            if metric not in core.index:
                continue
            for year_column in year_columns:
                period = f"{year_column[:4]}1231"
                primary = _numeric(core.at[metric, year_column])
                candidates_frame = abstract[
                    (abstract["period"] == period) & abstract["metric"].astype(str).isin(candidates)
                ]
                if primary is None or candidates_frame.empty:
                    continue
                secondary = _numeric(candidates_frame.iloc[0]["standardized_value"])
                if secondary is None:
                    continue
                compared += 1
                tolerance = max(1.0, abs(primary) * 0.005)
                if abs(primary - secondary) > tolerance:
                    mismatches.append(f"{metric}:{year_column}")
        add(
            "cross_source_reconciliation",
            "FAIL" if mismatches else ("PASS" if compared else "WARN"),
            (
                "mismatch: " + ", ".join(mismatches)
                if mismatches
                else (f"{compared} values agree within 0.5%" if compared else "no comparable values")
            ),
        )

    categories = set(segments.get("分类类型", pd.Series(dtype=str)).dropna().astype(str))
    missing_categories = {"按产品分类", "按地区分类"} - categories
    add(
        "segment_coverage",
        "WARN" if missing_categories else "PASS",
        "missing: " + ", ".join(sorted(missing_categories)) if missing_categories else "product and geography data available",
    )

    required_unit_datasets = {
        "statements_long",
        "core_actuals",
        "business_composition_long",
        "share_changes_long",
        "dividend_history_long",
    }
    covered_unit_datasets = set(unit_dictionary.get("dataset", pd.Series(dtype=str)).astype(str))
    missing_unit_datasets = sorted(required_unit_datasets - covered_unit_datasets)
    add(
        "unit_metadata",
        "WARN" if missing_unit_datasets else "PASS",
        "missing: " + ", ".join(missing_unit_datasets) if missing_unit_datasets else "original and standardized units documented",
    )

    annual_links = (
        disclosures[disclosures["公告标题"].astype(str).str.contains("年度报告", na=False)]
        if not disclosures.empty and "公告标题" in disclosures.columns
        else pd.DataFrame()
    )
    add(
        "official_report_links",
        "WARN" if annual_links.empty else "PASS",
        f"{len(annual_links)} annual-report records with CNInfo links",
    )

    failed_sources = [name for name, result in source_statuses.items() if result["status"] == "error"]
    add(
        "supplemental_sources",
        "WARN" if failed_sources else "PASS",
        "failed: " + ", ".join(failed_sources) if failed_sources else "all requested supplemental sources responded",
    )

    if any(check["status"] == "FAIL" for check in checks):
        grade = "FAIL"
    elif any(check["status"] == "WARN" for check in checks):
        grade = "WARN"
    else:
        grade = "PASS"
    return checks, grade


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def build_historical_financial_package(
    stock_code: str,
    years: int,
    output_dir: str,
    include_latest_interim: bool = True,
) -> dict:
    """Fetch, normalize, validate, and package A-share research inputs."""
    code = str(stock_code).strip()
    if not (code.isdigit() and len(code) == 6):
        raise ValueError("Historical package currently supports six-digit A-share codes only")
    if years < 3 or years > 10:
        raise ValueError("years must be between 3 and 10")

    generated_at = dt.datetime.now().astimezone()
    stamp = generated_at.strftime("%Y%m%dT%H%M%S%f")
    package_dir = Path(output_dir).expanduser().resolve() / f"{code}_historical_financial_package_{stamp}"
    package_dir.mkdir(parents=True, exist_ok=False)

    source_statuses: dict[str, dict] = {}
    snapshot = fetch_market_snapshot(code)
    raw_reports = fetch_raw_sina_reports(code)
    annual_reports = {name: _annual_frame(df, years) for name, df in raw_reports.items()}
    interim_reports = {
        name: _latest_interim_frame(df) if include_latest_interim else pd.DataFrame()
        for name, df in raw_reports.items()
    }

    annual_periods = {
        _period_key(period)
        for df in annual_reports.values()
        if not df.empty
        for period in df["报告日"].tolist()
    }
    interim_periods = {
        _period_key(period)
        for df in interim_reports.values()
        if not df.empty
        for period in df["报告日"].tolist()
    }
    allowed_periods = annual_periods | interim_periods
    start_year = min(int(period[:4]) for period in annual_periods) if annual_periods else generated_at.year - years
    start_date = f"{start_year}0101"
    end_date = generated_at.strftime("%Y%m%d")

    profile = _safe_fetch("company_profile", lambda: fetch_company_profile(code), source_statuses)
    segments_raw = _safe_fetch("business_composition", lambda: fetch_main_business_composition(code), source_statuses)
    abstract_raw = _safe_fetch("financial_abstract", lambda: fetch_financial_abstract(code), source_statuses)
    indicators_raw = _safe_fetch(
        "financial_indicators",
        lambda: fetch_financial_indicators(code, str(start_year)),
        source_statuses,
    )
    share_changes = _safe_fetch(
        "share_changes",
        lambda: fetch_share_changes(code, start_date, end_date),
        source_statuses,
    )
    dividends = _safe_fetch("dividend_history", lambda: fetch_dividend_history(code), source_statuses)

    disclosure_frames = []
    for category in ("年报", "半年报", "一季报", "三季报", "补充更正"):
        frame = _safe_fetch(
            f"disclosures_{category}",
            lambda category=category: fetch_disclosure_reports(code, category, start_date, end_date),
            source_statuses,
        )
        if not frame.empty:
            frame = frame.copy()
            frame.insert(0, "查询分类", category)
            disclosure_frames.append(frame)
    disclosures = (
        pd.concat(disclosure_frames, ignore_index=True).drop_duplicates()
        if disclosure_frames
        else pd.DataFrame()
    )

    statements_long = _statement_long(annual_reports, interim_reports)
    if not statements_long.empty:
        statements_long["source_url"] = statements_long["source_url_template"].map(
            lambda value: value.format(stock_code=code)
        )
        statements_long = statements_long.drop(columns=["source_url_template"])
    core_actuals = _build_core_actuals(annual_reports)
    segments = _filter_segments(segments_raw, start_year)
    abstract = _abstract_long(abstract_raw, allowed_periods)
    indicators = _indicators_long(indicators_raw, allowed_periods)
    segments_long = _segments_long(segments)
    share_changes_long = _share_changes_long(share_changes)
    dividends_long = _dividends_long(dividends)

    unit_sources = {
        "statements_long": statements_long,
        "core_actuals": core_actuals,
        "business_composition_long": segments_long,
        "financial_abstract_long": abstract,
        "financial_indicators_long": indicators,
        "share_changes_long": share_changes_long,
        "dividend_history_long": dividends_long,
    }
    unit_dictionary = _unit_dictionary(unit_sources)

    files: dict[str, str] = {}
    _write_csv(pd.DataFrame([snapshot]), package_dir / "market_snapshot.csv")
    files["market_snapshot"] = "market_snapshot.csv"
    for statement, filename in STATEMENT_FILES.items():
        annual = annual_reports.get(statement, pd.DataFrame())
        interim = interim_reports.get(statement, pd.DataFrame())
        combined = pd.concat([annual, interim], ignore_index=True) if not interim.empty else annual
        _write_csv(combined, package_dir / filename)
        files[statement] = filename
    datasets = {
        "statements_long": (statements_long, "statements_long.csv"),
        "core_actuals": (core_actuals, "core_actuals.csv"),
        "company_profile": (profile, "company_profile.csv"),
        "business_composition": (segments, "business_composition.csv"),
        "business_composition_long": (segments_long, "business_composition_long.csv"),
        "financial_abstract": (abstract, "financial_abstract_long.csv"),
        "financial_indicators": (indicators, "financial_indicators_long.csv"),
        "share_changes": (share_changes, "share_changes.csv"),
        "share_changes_long": (share_changes_long, "share_changes_long.csv"),
        "dividend_history": (dividends, "dividend_history.csv"),
        "dividend_history_long": (dividends_long, "dividend_history_long.csv"),
        "unit_dictionary": (unit_dictionary, "unit_dictionary.csv"),
        "source_manifest": (disclosures, "source_manifest.csv"),
    }
    for name, (df, filename) in datasets.items():
        _write_csv(df, package_dir / filename)
        files[name] = filename

    checks, grade = _quality_checks(
        snapshot,
        annual_reports,
        core_actuals,
        segments,
        abstract,
        unit_dictionary,
        disclosures,
        source_statuses,
    )
    quality_lines = [
        f"# {code} 历史财务数据包质量报告",
        "",
        f"- 生成时间：{generated_at.isoformat()}",
        f"- 覆盖年度：{', '.join(sorted(period[:4] for period in annual_periods)) or 'N/A'}",
        f"- 总体状态：**{grade}**",
        "",
        "## 自动检查",
        "",
        "| 检查项 | 状态 | 说明 |",
        "|---|---|---|",
    ]
    quality_lines.extend(
        f"| {check['check']} | {check['status']} | {check['detail']} |" for check in checks
    )
    quality_lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本数据包用于机械抽取、模型底稿和交叉核验，不替代公司定期报告。",
            "- 分部名称变更、追溯重述、异常项目和会计政策变化仍需回到巨潮年报核验。",
            "- 行情或股份数为 0 时视为不可用，不得进入估值。",
            "- 所有标准化换算均同时保留原值、原单位、标准单位和换算倍率；禁止脱离 unit_dictionary.csv 使用数值。",
        ]
    )
    (package_dir / "quality_report.md").write_text("\n".join(quality_lines), encoding="utf-8")
    files["quality_report"] = "quality_report.md"

    manifest = {
        "schema_version": "1.1.0",
        "stock_code": code,
        "generated_at": generated_at.isoformat(),
        "requested_years": years,
        "annual_periods": sorted(annual_periods),
        "latest_interim_periods": sorted(interim_periods),
        "quality_grade": grade,
        "files": files,
        "source_statuses": source_statuses,
        "checks": checks,
        "source_policy": {
            "statements": "新浪财经 via AkShare; verify material actuals against CNInfo filings",
            "segments": "东方财富 via AkShare",
            "official_links": "巨潮资讯 via AkShare",
            "market_data": "巨潮资讯/东方财富 via AkShare; zero means unavailable",
        },
    }
    files["manifest"] = "manifest.json"
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    archive_path = shutil.make_archive(str(package_dir), "zip", root_dir=package_dir)
    return {
        "status": "success",
        "stock_code": code,
        "quality_grade": grade,
        "annual_periods": sorted(annual_periods),
        "latest_interim_periods": sorted(interim_periods),
        "package_dir": os.path.abspath(package_dir),
        "manifest": os.path.abspath(package_dir / "manifest.json"),
        "quality_report": os.path.abspath(package_dir / "quality_report.md"),
        "archive": os.path.abspath(archive_path),
    }
