# HH520 Stable V2 — Single Source Edition

## 目标
以 HH520 `10023s.php` 为唯一正式采集入口，使用 Firecrawl 单页抓取，
经 Probability Layer、Value Layer、Decision Filter 和 GPT 分析后输出预测。

## 用户命令
`预测 YYYY-MM-DD 全部比赛`

## 固定 URL
`https://www.hh520.com/tx/10023s.php?riqi=YYYY-MM-DD&threshold=1&bankroll=5000`

## 正式预测流程
命令 → URL Builder → Cache → Firecrawl → Parser → Market Baseline →
Probability Layer → Value Layer → Decision Filter → GPT → 固定输出

## 研究验证流程
历史 10023s + 真实赛果 → Offline Evaluation → Baseline 对比 →
特征消融 → 决定是否进入 Stable

注意：研究验证不属于正式预测主流程，不自动改参数。

## 不使用
- 10013
- 10016
- 10017
- xi.php
- 数据库
- 自动训练
- 旧回测系统
