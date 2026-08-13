"""Optional free Futu OpenAPI adapter for HK revenue breakdowns.

The adapter is deliberately optional: the core MCP continues to run with
AkShare and yfinance only.  When the free Futu OpenD service and Python SDK are
available, it supplies structured product/industry/geography/business revenue
breakdowns in the issuer's original reporting currency.
"""

from __future__ import annotations

import os
import socket
from typing import Any

import pandas as pd


FUTU_REVENUE_BREAKDOWN_URL = (
    "https://openapi.futunn.com/futu-api-doc/quote/"
    "get-financials-revenue-breakdown.html"
)

SEGMENT_COLUMNS = [
    "period",
    "classification",
    "segment",
    "revenue",
    "ratio_pct",
    "currency",
    "original_unit",
    "standard_unit",
    "scale_to_standard",
    "unit_basis",
    "source_provider",
    "source_url",
]

SEGMENT_LONG_COLUMNS = [
    "period",
    "classification",
    "segment",
    "metric",
    "original_value",
    "standardized_value",
    "currency",
    "original_unit",
    "standard_unit",
    "scale_to_standard",
    "unit_basis",
    "source_provider",
    "source_url",
]


class FutuNotConfiguredError(RuntimeError):
    """Raised when the optional free Futu adapter is not locally available."""


def yahoo_to_futu_code(ticker: str) -> str:
    """Convert a Yahoo HK ticker such as ``0700.HK`` to ``HK.00700``."""
    text = str(ticker).strip().upper()
    raw = text[:-3] if text.endswith(".HK") else text
    if not raw.isdigit() or not 1 <= len(raw) <= 5:
        raise ValueError(f"Invalid HK ticker for Futu OpenAPI: {ticker}")
    return f"HK.{raw.lstrip('0').zfill(5)}"


def _connection_settings() -> tuple[str, int]:
    host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
    raw_port = os.environ.get("FUTU_OPEND_PORT", "11111")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise FutuNotConfiguredError(f"FUTU_OPEND_PORT is not an integer: {raw_port}") from exc
    return host, port


def _require_opend(host: str, port: int) -> None:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return
    except OSError as exc:
        raise FutuNotConfiguredError(
            f"free Futu OpenD is not reachable at {host}:{port}; "
            "start and log in to OpenD, or set FUTU_OPEND_HOST/FUTU_OPEND_PORT"
        ) from exc


def _enum_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    for attribute in ("value", "_value_"):
        candidate = getattr(value, attribute, None)
        if isinstance(candidate, (int, float)):
            return int(candidate)
    text = str(value)
    for number, token in ((1, "PRODUCT"), (2, "INDUSTRY"), (4, "REGION"), (8, "BUSINESS")):
        if token in text.upper():
            return number
    return None


def _classification(value: Any) -> str:
    return {
        1: "product",
        2: "industry",
        4: "geography",
        8: "business",
    }.get(_enum_number(value), f"unknown:{value}")


def _normalise_response(data: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    period = str(data.get("period") or "N/A")
    currency = str(data.get("currency_code") or "UNRESOLVED").upper()
    for group in data.get("breakdown_list") or []:
        classification = _classification(group.get("type"))
        for item in group.get("item_list") or []:
            revenue = pd.to_numeric(pd.Series([item.get("main_oper_income")]), errors="coerce").iloc[0]
            ratio = pd.to_numeric(pd.Series([item.get("ratio")]), errors="coerce").iloc[0]
            rows.append(
                {
                    "period": period,
                    "classification": classification,
                    "segment": item.get("name"),
                    "revenue": None if pd.isna(revenue) else float(revenue),
                    "ratio_pct": None if pd.isna(ratio) else float(ratio),
                    "currency": currency,
                    "original_unit": "currency",
                    "standard_unit": "currency",
                    "scale_to_standard": 1.0,
                    "unit_basis": "Futu OpenAPI original-currency revenue; currency_code omitted",
                    "source_provider": "Futu OpenAPI (free OpenD login)",
                    "source_url": FUTU_REVENUE_BREAKDOWN_URL,
                }
            )
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def fetch_hk_revenue_breakdown_history(ticker: str, years: int = 5) -> pd.DataFrame:
    """Fetch up to ``years`` annual HK revenue breakdown periods from Futu.

    Futu documents that omitting ``currency_code`` returns original-currency
    data.  The function therefore never requests a converted display currency.
    It requires the free local OpenD login but no paid data subscription.
    """
    try:
        from futu import OpenQuoteContext, RET_OK
    except ImportError as exc:
        raise FutuNotConfiguredError(
            "optional futu-api SDK is not installed; run `pip install futu-api` "
            "after installing the free Futu OpenD client"
        ) from exc

    host, port = _connection_settings()
    _require_opend(host, port)
    quote_ctx = OpenQuoteContext(host=host, port=port)
    code = yahoo_to_futu_code(ticker)
    try:
        ret, latest = quote_ctx.get_financials_revenue_breakdown(code)
        if ret != RET_OK:
            raise RuntimeError(f"Futu revenue breakdown failed for {code}: {latest}")
        if not isinstance(latest, dict):
            raise RuntimeError(f"Unexpected Futu response type for {code}: {type(latest).__name__}")

        screen_dates = latest.get("screen_date_list") or []
        annual_dates = sorted([
            item for item in screen_dates
            if str(item.get("period_text") or "").upper().endswith("/FY")
        ], key=lambda item: int(item.get("date") or 0), reverse=True)[:years]
        responses: list[dict[str, Any]] = []
        if annual_dates:
            for item in annual_dates:
                ret, response = quote_ctx.get_financials_revenue_breakdown(code, date=int(item["date"]))
                if ret != RET_OK:
                    continue
                if isinstance(response, dict):
                    responses.append(response)
        else:
            responses.append(latest)

        frames = [_normalise_response(response) for response in responses]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return pd.DataFrame(columns=SEGMENT_COLUMNS)
        result = pd.concat(frames, ignore_index=True)
        return result.drop_duplicates(
            subset=["period", "classification", "segment"], keep="first"
        ).reset_index(drop=True)
    finally:
        quote_ctx.close()


def revenue_breakdown_to_long(segments: pd.DataFrame) -> pd.DataFrame:
    """Convert one-row-per-segment Futu output to the MCP metric-long schema."""
    if segments.empty:
        return pd.DataFrame(columns=SEGMENT_LONG_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, source in segments.iterrows():
        common = {
            "period": source.get("period"),
            "classification": source.get("classification"),
            "segment": source.get("segment"),
            "scale_to_standard": 1.0,
            "source_provider": source.get("source_provider"),
            "source_url": source.get("source_url"),
        }
        rows.append(
            {
                **common,
                "metric": "revenue",
                "original_value": source.get("revenue"),
                "standardized_value": source.get("revenue"),
                "currency": source.get("currency"),
                "original_unit": "currency",
                "standard_unit": "currency",
                "unit_basis": source.get("unit_basis"),
            }
        )
        rows.append(
            {
                **common,
                "metric": "revenue_ratio",
                "original_value": source.get("ratio_pct"),
                "standardized_value": source.get("ratio_pct"),
                "currency": "N/A",
                "original_unit": "%",
                "standard_unit": "%",
                "unit_basis": "Futu OpenAPI percentage value; 12.34 means 12.34%",
            }
        )
    return pd.DataFrame(rows, columns=SEGMENT_LONG_COLUMNS)
