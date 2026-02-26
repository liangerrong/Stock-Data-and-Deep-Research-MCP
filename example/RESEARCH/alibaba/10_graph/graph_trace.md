# GoT图谱轨迹记录 (Graph Trace)

## 图谱演化概览

研究过程中GoT图谱经历3次主要状态更新，节点置信度和边权重随数据收集逐步修正。

---

## 初始状态 (Phase 1 Init)

```
nodes: 12 | edges: 15
hypothesis confidence: H1=65% H2=55% H3=40% H4=50% H5=60%
```

### 节点初始化
| Node | 名称          | 初始状态          |
| ---- | ------------- | ----------------- |
| N1   | 淘天集团      | stub — 待年报填充 |
| N2   | AIDC国际      | stub              |
| N3   | 云智能        | stub              |
| N4   | 菜鸟          | stub              |
| N5   | 本地生活      | stub              |
| N6   | 虎鲸文娱+其他 | stub              |
| N7   | 集团财务      | stub              |
| N8   | 资本配置      | stub              |
| N9   | 电商竞争      | stub              |
| N10  | 云竞争        | stub              |
| N11  | AI战略        | stub              |
| N12  | 风险因素      | stub              |

---

## Iteration 1 更新 (Phase 3)

**触发**: 年报pp1-105深度阅读 + Web搜索14条query

### 节点状态变更
| Node | 变更              | 关键数据注入                                  |
| ---- | ----------------- | --------------------------------------------- |
| N1   | stub → **filled** | 收入4,498亿/EBITA 1,962亿/CMR 3,224亿(+6%)    |
| N2   | stub → **filled** | 收入1,323亿(+29%)/EBITA -151亿/FY26Q2首次盈利 |
| N3   | stub → **filled** | 收入1,180亿(+11%)/EBITA 106亿(+72%)/Q2+34%    |
| N4   | stub → **filled** | 收入1,013亿/EBITA 3亿                         |
| N5   | stub → **filled** | 收入671亿(+12%)/EBITA -37亿/外卖三方混战      |
| N6   | stub → **filled** | 收入223亿/EBITA -6亿                          |
| N7   | stub → **filled** | 总收入9,963亿/净利1,260亿/FCF 739亿           |
| N8   | stub → **filled** | 回购$119亿/分红$46亿/可用现金5,971亿          |
| N9   | stub → **filled** | 5军GMV/份额37.3%/PDD JD MT财务对比            |
| N10  | stub → **filled** | IaaS 26.1%#1/华为云追赶/运营商云上升          |
| N11  | stub → **filled** | 3年≥3,800亿/Qwen3 6亿下载/数据中心20GW目标    |
| N12  | stub → **filled** | VIE/地缘/AI ROI/外卖补贴/宏观消费             |

### 假设置信度更新
```
H1: 65% → 60% (↓5)  CMR+6%✓ 但份额37%↓
H2: 55% → 60% (↑5)  EBITA+72%↑ + Q2收入+34%
H3: 40% → 55% (↑15) FY26Q2首次盈利✓ 里程碑
H4: 50% → 40% (↓10) FCF 739亿(-53%) + 3年CapEx≥3800亿
H5: 60% → 65% (↑5)  SOTP $5,751亿 vs 市值$3,878亿 (+48%)
```

### 新增/强化边
| From   | To       | 变更    | 原因                     |
| ------ | -------- | ------- | ------------------------ |
| N11→N3 | weight ↑ | 0.7→0.9 | AI是云增长核心驱动力     |
| N11→N7 | weight ↑ | 0.5→0.8 | AI CapEx直接影响FCF      |
| N9→N1  | weight ↑ | 0.6→0.8 | 竞争压力是淘天核心变量   |
| N5→N7  | **new**  | 0.7     | 外卖补贴大战侵蚀集团利润 |

---

## 矛盾处理 (Phase 4)

识别5个矛盾，4个已解析:

| ID  | 矛盾                     | 解析                        | 影响节点    |
| --- | ------------------------ | --------------------------- | ----------- |
| C1  | 份额↓ vs CMR收入↑        | Take rate提升 + GMV绝对值增 | N1, N9      |
| C2  | GAAP+77% vs Non-GAAP持平 | 减值低基数效应              | N7          |
| C3  | FCF-53% vs OCF仅-10%     | AI CapEx 860亿激增          | N7, N8, N11 |
| C4  | 外卖份额数据不一         | 口径差异/JPM数据最可信      | N5          |
| C5  | 分析师$198 vs 实际风险   | Sell-side bias/需独立验证   | N7, N12     |

---

## 终态快照

```
graph_completeness: 12/12 nodes filled (100%)
edges: 15 initial + 1 new = 16 total
contradictions: 5 identified / 4 resolved / 1 pending
hypothesis_confidence: H1=60% H2=60% H3=55% H4=40% H5=65%
qa_grade: A-
```

---

*轨迹记录截至 2026-02-10*
