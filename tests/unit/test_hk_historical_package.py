import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.core.historical_package import build_historical_financial_package
from src.core.hk_historical_package import normalize_hk_ticker


PERIODS = ["20231231", "20221231", "20211231"]


def _annual_reports(currency: str = "USD") -> dict[str, pd.DataFrame]:
    metadata = {
        "报告日": PERIODS,
        "数据源": ["Yahoo Finance via yfinance"] * 3,
        "是否审计": ["未确认"] * 3,
        "公告日期": [pd.NA] * 3,
        "币种": [currency] * 3,
        "币种来源": ["Yahoo Finance info.financialCurrency"] * 3,
        "类型": ["合并口径未确认"] * 3,
    }
    return {
        "利润表": pd.DataFrame({
            **metadata,
            "Total Revenue": [1_000.0, 900.0, 800.0],
            "Cost Of Revenue": [600.0, 550.0, 500.0],
            "Net Income": [120.0, 100.0, 80.0],
        }),
        "资产负债表": pd.DataFrame({
            **metadata,
            "Total Assets": [2_000.0, 1_800.0, 1_600.0],
            "Total Liabilities Net Minority Interest": [800.0, 750.0, 700.0],
            "Total Equity Gross Minority Interest": [1_200.0, 1_050.0, 900.0],
        }),
        "现金流量表": pd.DataFrame({
            **metadata,
            "Operating Cash Flow": [160.0, 140.0, 120.0],
            "Capital Expenditure": [-50.0, -45.0, -40.0],
        }),
    }


def test_normalizes_hk_codes():
    assert normalize_hk_ticker("0700.HK") == ("0700.HK", "00700")
    assert normalize_hk_ticker("00700") == ("0700.HK", "00700")
    assert normalize_hk_ticker("5.HK") == ("0005.HK", "00005")


def test_builds_hk_package_without_mixing_quote_and_financial_currency(tmp_path):
    reports = _annual_reports("USD")
    report_metadata = pd.DataFrame({
        "REPORT_DATE": ["2023-12-31"],
        "CURRENCY": ["美元"],
        "REPORT_TYPE": ["年报"],
    })
    provider_reports = {
        "利润表": pd.DataFrame({
            "REPORT_DATE": ["2023-12-31"],
            "STD_ITEM_NAME": ["经营收入总额"],
            "AMOUNT": [7_800.0],
        }),
        "资产负债表": pd.DataFrame(),
        "现金流量表": pd.DataFrame(),
    }
    indicators = pd.DataFrame({
        "REPORT_DATE": ["2023-12-31"],
        "CURRENCY": ["HKD"],
        "IS_CNY_CODE": [0],
        "OPERATE_INCOME": [7_800.0],
    })
    dividends = pd.DataFrame({
        "最新公告日期": ["2024-03-01"],
        "财政年度": [2023],
        "分红方案": ["每股派美元0.1元(相当于港币0.78元)"],
        "分配类型": ["年度分配"],
    })
    identity = {
        "ticker": "0005.HK",
        "market": "HK",
        "exchange": "HKG",
        "short_name": "HSBC",
        "long_name": "HSBC Holdings plc",
        "quote_currency": "HKD",
        "financial_currency": "USD",
        "instrument_type": "EQUITY",
        "shares_outstanding": 1_000.0,
        "metadata_source": "Yahoo Finance info via yfinance",
    }
    snapshot = {
        "stock_code": "0005.HK",
        "stock_name": "HSBC",
        "current_price": 100.0,
        "circulating_shares": 1_000.0,
        "shares_outstanding": 1_000.0,
        "currency": "HKD",
        "quote_currency": "HKD",
        "financial_currency": "USD",
    }
    with (
        patch("src.core.hk_historical_package.create_ticker_obj", return_value=object()),
        patch("src.core.hk_historical_package.fetch_hk_security_metadata", return_value=identity),
        patch("src.core.hk_historical_package.fetch_hk_market_snapshot", return_value=snapshot),
        patch("src.core.hk_historical_package.fetch_hk_raw_reports", side_effect=[reports, {name: pd.DataFrame() for name in reports}]),
        patch("src.core.hk_historical_package.fetch_hk_report_metadata", return_value=report_metadata),
        patch("src.core.hk_historical_package.fetch_hk_company_profile", return_value=pd.DataFrame({"公司名称": ["HSBC Holdings plc"]})),
        patch("src.core.hk_historical_package.fetch_hk_security_profile", return_value=pd.DataFrame({"证券代码": ["00005.HK"]})),
        patch("src.core.hk_historical_package.fetch_hk_financial_indicators", return_value=indicators),
        patch("src.core.hk_historical_package.fetch_hk_dividend_history", return_value=dividends),
        patch("src.core.hk_historical_package.fetch_hk_provider_reports", return_value=provider_reports),
    ):
        result = build_historical_financial_package("0005.HK", 3, str(tmp_path), True)

    package_dir = Path(result["package_dir"])
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    statements = pd.read_csv(package_dir / "statements_long.csv")
    provider = pd.read_csv(package_dir / "provider_statements_long.csv")
    currencies = pd.read_csv(package_dir / "currency_manifest.csv")
    dividends_long = pd.read_csv(package_dir / "dividend_history_long.csv")

    assert result["stock_code"] == "0005.HK"
    assert result["quote_currency"] == "HKD"
    assert result["financial_currency"] == "USD"
    assert set(statements["currency"]) == {"USD"}
    assert set(provider["currency"]) == {"UNRESOLVED"}
    assert provider.iloc[0]["issuer_reported_currency"] == "USD"
    assert provider.iloc[0]["provider_claimed_currency"] == "HKD"
    assert set(currencies["currency"]) >= {"HKD", "USD", "UNRESOLVED"}
    assert set(dividends_long["currency"]) == {"USD", "HKD"}
    assert manifest["schema_version"] == "2.0.0"
    assert manifest["market"] == "HK"
    assert manifest["source_policy"]["provider_cross_check"].endswith("excluded from modeling")


def test_hk_cny_financial_currency_is_not_overwritten_by_hkd_quote(tmp_path):
    reports = _annual_reports("CNY")
    identity = {
        "ticker": "0700.HK", "market": "HK", "exchange": "HKG",
        "short_name": "Tencent", "long_name": "Tencent Holdings Limited",
        "quote_currency": "HKD", "financial_currency": "CNY",
        "instrument_type": "EQUITY", "shares_outstanding": 1_000.0,
        "metadata_source": "Yahoo Finance info via yfinance",
    }
    snapshot = {
        "stock_code": "0700.HK", "stock_name": "Tencent", "current_price": 500.0,
        "circulating_shares": 1_000.0, "shares_outstanding": 1_000.0,
        "currency": "HKD", "quote_currency": "HKD", "financial_currency": "CNY",
    }
    with (
        patch("src.core.hk_historical_package.create_ticker_obj", return_value=object()),
        patch("src.core.hk_historical_package.fetch_hk_security_metadata", return_value=identity),
        patch("src.core.hk_historical_package.fetch_hk_market_snapshot", return_value=snapshot),
        patch("src.core.hk_historical_package.fetch_hk_raw_reports", side_effect=[reports, {name: pd.DataFrame() for name in reports}]),
        patch("src.core.hk_historical_package.fetch_hk_report_metadata", return_value=pd.DataFrame()),
        patch("src.core.hk_historical_package.fetch_hk_company_profile", return_value=pd.DataFrame()),
        patch("src.core.hk_historical_package.fetch_hk_security_profile", return_value=pd.DataFrame()),
        patch("src.core.hk_historical_package.fetch_hk_financial_indicators", return_value=pd.DataFrame()),
        patch("src.core.hk_historical_package.fetch_hk_dividend_history", return_value=pd.DataFrame()),
        patch("src.core.hk_historical_package.fetch_hk_provider_reports", return_value={name: pd.DataFrame() for name in reports}),
    ):
        result = build_historical_financial_package("0700.HK", 3, str(tmp_path), True)
    statements = pd.read_csv(Path(result["package_dir"]) / "statements_long.csv")
    assert result["quote_currency"] == "HKD"
    assert result["financial_currency"] == "CNY"
    assert set(statements["currency"]) == {"CNY"}
