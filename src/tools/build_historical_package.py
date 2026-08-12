"""MCP handler for the auditable A-share historical financial package."""

import json

from src.core.historical_package import build_historical_financial_package
from src.tools.get_financials import get_output_dir


def handle_build_historical_package(
    stock_code: str,
    years: int = 5,
    output_dir: str | None = None,
    include_latest_interim: bool = True,
) -> str:
    try:
        actual_output_dir = get_output_dir(output_dir)
        result = build_historical_financial_package(
            stock_code=stock_code,
            years=years,
            output_dir=actual_output_dir,
            include_latest_interim=include_latest_interim,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except ValueError as exc:
        return json.dumps(
            {"status": "error", "error": str(exc)},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"status": "error", "error": f"Unexpected package build failure: {exc}"},
            ensure_ascii=False,
        )
