import pytest

from src.core.futu_client import (
    _normalise_response,
    revenue_breakdown_to_long,
    yahoo_to_futu_code,
)


def test_yahoo_to_futu_code():
    assert yahoo_to_futu_code("0700.HK") == "HK.00700"
    assert yahoo_to_futu_code("0005.HK") == "HK.00005"
    assert yahoo_to_futu_code("00700") == "HK.00700"
    with pytest.raises(ValueError):
        yahoo_to_futu_code("HSBC")


def test_normalises_original_currency_revenue_breakdown():
    response = {
        "period": "2025/FY",
        "currency_code": "CNY",
        "breakdown_list": [
            {
                "type": 1,
                "item_list": [
                    {"name": "Value-added services", "main_oper_income": 369_281_000_000, "ratio": 49.1218},
                ],
            },
            {
                "type": 4,
                "item_list": [
                    {"name": "China", "main_oper_income": 600_000_000_000, "ratio": 79.81},
                ],
            },
        ],
    }
    segments = _normalise_response(response)
    assert set(segments["classification"]) == {"product", "geography"}
    assert set(segments["currency"]) == {"CNY"}
    assert segments.loc[segments["classification"] == "product", "revenue"].iloc[0] == 369_281_000_000

    long = revenue_breakdown_to_long(segments)
    assert set(long["metric"]) == {"revenue", "revenue_ratio"}
    assert set(long.loc[long["metric"] == "revenue", "currency"]) == {"CNY"}
    assert set(long.loc[long["metric"] == "revenue_ratio", "currency"]) == {"N/A"}
