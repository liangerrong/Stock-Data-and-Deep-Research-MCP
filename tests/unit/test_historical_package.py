import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.core.historical_package import build_historical_financial_package


PERIODS = ["20231231", "20221231", "20211231"]


def _income_statement() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "报告日": PERIODS,
            "营业收入": [1_000.0, 900.0, 800.0],
            "营业成本": [600.0, 550.0, 500.0],
            "净利润": [120.0, 100.0, 80.0],
            "归属于母公司所有者的净利润": [115.0, 96.0, 77.0],
            "是否审计": ["是"] * 3,
            "公告日期": ["20240401", "20230401", "20220401"],
            "币种": ["CNY"] * 3,
            "类型": ["合并"] * 3,
        }
    )


def _balance_sheet() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "报告日": PERIODS,
            "资产总计": [2_000.0, 1_800.0, 1_600.0],
            "负债合计": [800.0, 750.0, 700.0],
            "所有者权益(或股东权益)合计": [1_200.0, 1_050.0, 900.0],
            "负债和所有者权益(或股东权益)总计": [2_000.0, 1_800.0, 1_600.0],
            "是否审计": ["是"] * 3,
            "公告日期": ["20240401", "20230401", "20220401"],
            "币种": ["CNY"] * 3,
            "类型": ["合并"] * 3,
        }
    )


def _cash_flow_statement() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "报告日": PERIODS,
            "经营活动产生的现金流量净额": [160.0, 140.0, 120.0],
            "购建固定资产、无形资产和其他长期资产所支付的现金": [50.0, 45.0, 40.0],
            "期初现金及现金等价物余额": [200.0, 180.0, 160.0],
            "现金及现金等价物净增加额": [20.0, 20.0, 20.0],
            "期末现金及现金等价物余额": [220.0, 200.0, 180.0],
            "是否审计": ["是"] * 3,
            "公告日期": ["20240401", "20230401", "20220401"],
            "币种": ["CNY"] * 3,
            "类型": ["合并"] * 3,
        }
    )


def _abstract() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "选项": ["常用指标", "常用指标"],
            "指标": ["营业总收入", "净利润"],
            "2023-12-31": [1_000.0, 120.0],
            "2022-12-31": [900.0, 100.0],
            "2021-12-31": [800.0, 80.0],
        }
    )


def _build(tmp_path: Path, current_price: float = 10.0) -> dict:
    reports = {
        "资产负债表": _balance_sheet(),
        "利润表": _income_statement(),
        "现金流量表": _cash_flow_statement(),
    }
    segments = pd.DataFrame(
        {
            "报告日期": ["2023-12-31", "2023-12-31"],
            "分类类型": ["按产品分类", "按地区分类"],
            "主营构成": ["产品甲", "境内"],
            "主营收入": [800.0, 1_000.0],
            "收入比例": [0.8, 1.0],
        }
    )
    disclosures = pd.DataFrame(
        {
            "公告标题": ["测试公司2023年年度报告"],
            "公告时间": ["2024-04-01"],
            "公告链接": ["https://www.cninfo.com.cn/example.pdf"],
        }
    )
    with (
        patch("src.core.historical_package.fetch_market_snapshot", return_value={
            "stock_code": "000001",
            "stock_name": "测试公司",
            "current_price": current_price,
            "circulating_shares": 1_000.0,
        }),
        patch("src.core.historical_package.fetch_raw_sina_reports", return_value=reports),
        patch("src.core.historical_package.fetch_company_profile", return_value=pd.DataFrame({"公司简称": ["测试公司"]})),
        patch("src.core.historical_package.fetch_main_business_composition", return_value=segments),
        patch("src.core.historical_package.fetch_financial_abstract", return_value=_abstract()),
        patch("src.core.historical_package.fetch_financial_indicators", return_value=pd.DataFrame({"日期": PERIODS, "净资产收益率": [12.0, 11.0, 10.0]})),
        patch("src.core.historical_package.fetch_share_changes", return_value=pd.DataFrame({"变动日期": ["2023-12-31"], "总股本": [1_200.0]})),
        patch("src.core.historical_package.fetch_dividend_history", return_value=pd.DataFrame({"报告期": ["2023年报"], "现金分红-现金分红比例": [10.0]})),
        patch("src.core.historical_package.fetch_disclosure_reports", return_value=disclosures),
    ):
        return build_historical_financial_package("000001", 3, str(tmp_path), False)


def test_builds_auditable_package_with_expected_files(tmp_path):
    result = _build(tmp_path)

    assert result["status"] == "success"
    assert result["quality_grade"] == "PASS"
    assert result["annual_periods"] == PERIODS[::-1]
    package_dir = Path(result["package_dir"])
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    expected_files = {
        "balance_sheet.csv",
        "income_statement.csv",
        "cash_flow_statement.csv",
        "statements_long.csv",
        "core_actuals.csv",
        "business_composition.csv",
        "business_composition_long.csv",
        "share_changes_long.csv",
        "dividend_history_long.csv",
        "unit_dictionary.csv",
        "source_manifest.csv",
        "quality_report.md",
        "manifest.json",
    }
    assert expected_files.issubset({path.name for path in package_dir.iterdir()})
    assert manifest["files"]["manifest"] == "manifest.json"
    assert all(check["status"] == "PASS" for check in manifest["checks"])

    long_data = pd.read_csv(package_dir / "statements_long.csv")
    assert set(long_data["statement"]) == {"资产负债表", "利润表", "现金流量表"}
    assert long_data["source_url"].str.contains("000001").all()
    assert set(["original_value", "standardized_value", "currency", "original_unit", "standard_unit", "scale_to_standard"]).issubset(long_data.columns)

    units = pd.read_csv(package_dir / "unit_dictionary.csv")
    assert {"元", "元/股", "%", "股"}.issubset(set(units["standard_unit"]))

    core_actuals = pd.read_csv(package_dir / "core_actuals.csv").set_index("metric")
    assert core_actuals.at["自由现金流", "2023A"] == 110.0

    segment_long = pd.read_csv(package_dir / "business_composition_long.csv")
    revenue_ratio = segment_long[segment_long["metric"] == "收入比例"].iloc[0]
    assert revenue_ratio["scale_to_standard"] == 100.0

    share_long = pd.read_csv(package_dir / "share_changes_long.csv")
    total_shares = share_long[share_long["metric"] == "总股本"].iloc[0]
    assert total_shares["original_unit"] == "万股"
    assert total_shares["standard_unit"] == "股"
    assert total_shares["standardized_value"] == 12_000_000.0

    with zipfile.ZipFile(result["archive"]) as archive:
        assert "manifest.json" in archive.namelist()


def test_zero_market_snapshot_is_warned_not_used(tmp_path):
    result = _build(tmp_path, current_price=0.0)
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

    market_check = next(check for check in manifest["checks"] if check["check"] == "market_snapshot")
    assert result["quality_grade"] == "WARN"
    assert market_check["status"] == "WARN"


def test_rejects_invalid_market_code(tmp_path):
    try:
        build_historical_financial_package("NOT-A-CODE", 3, str(tmp_path))
    except ValueError as exc:
        assert "A-share code or an HK code" in str(exc)
    else:
        raise AssertionError("Expected invalid market code to be rejected")
