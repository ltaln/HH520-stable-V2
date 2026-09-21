# HH520 Stable V2.1 — 10027s + Decision Filter V2

## 目标
以 HH520 `10027s.php` 为唯一正式采集入口，使用 Firecrawl 单页抓取，
经 Probability Layer、Value Layer、Decision Filter V2 和 GPT 分析后输出预测。

## 用户命令
`预测 YYYY-MM-DD 全部比赛`

## 固定 URL
`https://www.hh520.com/tx/10027s.php?riqi_start=YYYY-MM-DD&riqi_end=YYYY-MM-DD&threshold=1&bankroll=5000`

## 正式预测流程
命令 → 10027s URL Builder → Cache → Firecrawl → 10027s Parser →
Market Baseline → Probability Layer → Value Layer → Decision Filter V2 →
GPT → 固定输出

## Decision Filter V2
Decision Filter V2 使用 2026-08 Discovery + 2026-09-01..20 Historical Shadow
验证后的跨时间窗因子，只负责最终放行 / PASS，不改变 Probability Layer
的方向，也不允许 Value Layer 单独决定胜平负。

当前 Hard PASS：
- 概率集中度 <40%
- pattern = ⚡ 极端

正式输出保留：
- Stable V2 原始方向
- Stable V2.1 Decision Filter 决策
- BET_CANDIDATE / PASS
- Filter 分数与原因

## 10027s 数据语义
- 基础表中的半场比分、全场比分属于真实赛果标签。
- 已结束比赛不得把这些赛果字段送入赛前预测。
- 融合表中的单选、融合真实概率、半全场及研究因子可作为赛前结构化字段。
- 比分/总进球若为研究推导，必须明确标记为派生结果，不得冒充 HH520 原始预测。

## 研究验证流程
Historical Research / Hidden Model Reverse / Shadow / Forward 独立运行。
Research 不得自动修改 Stable；任何后续规则晋级仍需人工审核。

## 不使用
- 10013
- 10016
- 10017
- xi.php
- 长期数据库
- 自动训练
