# HH520 Stable V3.2

## 目标
以 HH520 `10027s.php` 为唯一正式采集入口，通过 Firecrawl 单页抓取，
由冻结的 Stable V3.2 本地模型完成胜平负、半全场、比分、总进球与置信等级输出。

## 用户命令
`预测 YYYY-MM-DD 全部比赛`

## 固定 URL
`https://www.hh520.com/tx/10027s.php?riqi_start=YYYY-MM-DD&riqi_end=YYYY-MM-DD&threshold=1&bankroll=5000`

## 正式预测流程
命令 → 10027s URL Builder → Cache → Firecrawl → 10027s Parser →
Market Baseline → WDL → Research Confidence → HTFT → Pooled Poisson Score →
Decision Filter V3.2 → 固定输出 → GPT 可选解释审核

## Stable V3.2
- WDL：`MARKET_PROPORTIONAL_DEVIG`
- page_probability：仅审计，不参与正式方向
- S级筛选：`market pmax >= 0.73`
- HTFT：`CONDITIONAL_HT_GIVEN_FT`
- Score：`POOLED_POISSON`
- GPT：`EXPLANATION_ONLY`
- Stable 自动调参：禁止

## 输出
每场保留：
- 胜平负
- 市场概率
- 置信等级 S / NORMAL
- 比分 Top2
- 半全场 Top2
- 总进球
- 置信度
- Decision Filter：BET_CANDIDATE / PASS
- 一致性提示（若比分 Top2 与 WDL 方向不一致）

## 10027s 数据语义
- 基础表中的半场比分、全场比分属于真实赛果标签。
- 已结束比赛不得把赛果字段送入赛前推理。
- 赔率、控球、进攻、防守、交锋、状态等赛前结构字段可用于冻结模型。
- “建议下注”“是否下注”不得作为正式预测输入。
- 页面融合概率不得覆盖正式市场 WDL。

## 模型文件
`model_artifacts/HH520_Stable_V3_2.json`

冻结训练区间：
- 2026-05-01 至 2026-09-20
- 1432 场

9月1-20日已参与开发与压力测试，不再视为 untouched final test。

## 研究验证
Historical Research / Hidden Model Reverse / Shadow / Forward 独立运行。
Research 只能生成 Candidate；任何升级必须人工审核后进入 Stable。

## 不使用
- 10013
- 10016
- 10017
- xi.php
- 长期数据库
- 自动训练/自动晋升
