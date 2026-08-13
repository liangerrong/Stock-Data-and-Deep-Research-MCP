# 港股币种语义与处理规则

核验日期：2026-08-13。

## 结论

港股的交易币种通常是港元，但发行人财报可以使用人民币、美元或港元。MCP 必须分开保存：

- `quote_currency`：Yahoo Finance `info.currency`，只用于股价、市值等市场数据。
- `financial_currency`：Yahoo Finance `info.financialCurrency`，用于 Yahoo Finance 三张财务报表。
- 东方财富港股金额：报告列表、主要指标和实际金额行为无法证明使用同一币种，因此默认不再抓取；兼容数据集保持为空。

## 接口证据

### Yahoo Finance / yfinance

yfinance 的公开接口同时提供 `Ticker.get_info()` 以及年度/季度三表。实测同一证券的 `info.currency` 与 `info.financialCurrency` 可以不同：

| Ticker | `currency` | `financialCurrency` |
|---|---|---|
| 0700.HK 腾讯 | HKD | CNY |
| 0005.HK 汇丰 | HKD | USD |
| 0388.HK 港交所 | HKD | HKD |
| 1299.HK 友邦 | HKD | USD |

因此本项目把 `financialCurrency` 继承到每一条 Yahoo 财务报表记录，并在 `currency_basis` 中保留来源。yfinance 是 Yahoo Finance 公共接口的开源封装，不是发行人或交易所一级来源，最终审计仍需回到年报。

### AKShare / 东方财富

AKShare 的 `stock_financial_hk_report_em` 先读取报告列表，其中包含 `CURRENCY`、`ACCOUNT_STANDARD` 和 `REPORT_TYPE`；随后读取三表行项目，但行项目响应只请求 `AMOUNT`，没有逐金额币种字段。

实测报告列表能够反映发行人报告币种：腾讯为人民币、汇丰和友邦为美元、港交所为港元。但 `stock_financial_hk_analysis_indicator_em` 对这些公司又返回 `CURRENCY=HKD`。同时，腾讯 2025 年东方财富营运收入金额与 Yahoo 的人民币金额完全一致，而美元报告公司的若干展示金额表现出港币换算特征。

这说明不能仅凭港股上市地、报告列表币种或主要指标的 `CURRENCY` 字段，断言所有东方财富行项目金额均为港元或发行人原币。因此本项目采取保守规则：

1. 当前默认路由不再请求东方财富港股金额、主要指标或报告币种元数据。
2. `provider_statements_long.csv`、`financial_indicators_long.csv` 和 `hk_report_metadata.csv` 仅保留兼容表头。
3. `core_actuals.csv` 只由 yfinance 三表生成，不混入东方财富金额。
4. 东方财富仍可用于公司资料，以及分红方案中明确写出的币种文字。

## 当前机械化边界

- Yahoo Finance 通常可提供五个年度列，但个别公司季度表可能为空或不足。
- 东方财富分红方案文字通常明确声明港币、美元等币种，可逐条解析，不继承财报币种。
- 港股产品/地区分部没有可靠的现成 AKShare 或 yfinance 接口。MCP 可选连接免费的 Futu OpenD 获取发行人披露的收入及占比；未配置、未披露或历史期不足时保持空表并输出 `WARN`。
- Futu 分部接口不提供通用的分部成本和分部利润，且仍需与发行人年报核对。

## 参考入口

- yfinance API：<https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html>
- Futu 主营构成 API：<https://openapi.futunn.com/futu-api-doc/quote/get-financials-revenue-breakdown.html>
- Futu 免费登录及行情权限：<https://openapi.futunn.com/futu-api-doc/intro/authority.html>
- AKShare 股票接口：<https://akshare.akfamily.xyz/data/stock/stock.html>
- 东方财富港股财务分析：<https://emweb.securities.eastmoney.com/PC_HKF10/FinancialAnalysis/index>
- 香港交易所披露易：<https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh>
