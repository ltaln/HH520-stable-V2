# HH520 Stable V3.3

## 目标
正式基础数据源固定为 HH520 `10027s.php`。V3.3 在保留市场去水基线的前提下，增加比赛状态识别、市场冲突保险、Tail 场景、跨层一致性、概率展示和可选半全场分时数据。

## 用户命令
`预测 YYYY-MM-DD 全部比赛`

## 正式流程
命令 → 10027s Cache/Firecrawl → Parser → Market De-vig →
State Engine → Market Conflict/Insurance → Primary/Alternate Scenario →
Conditional HTFT (+ optional goal-timing reweight) →
Pooled Poisson Score → Cross-layer Consistency → Calibration diagnostics →
6列正式输出 → GPT解释审核

## V3.3 核心规则
- WDL 主锚仍是 `MARKET_PROPORTIONAL_DEVIG`。
- page_probability 不直接覆盖市场方向，只作为独立确认/冲突证据。
- State：`CONFIRMED / STANDARD / BALANCED / CONFLICT / TAIL_ALERT`。
- Balanced 不自动判平。
- Conflict/Tail 不自动反市场；主场景与尾部场景分层。
- HTFT 基线仍为 `CONDITIONAL_HT_GIVEN_FT`。
- 若取得六段进失球数据，只重权 HT 条件分布，并保持每个 FT 边际概率不变。
- Score 仍为 `POOLED_POISSON`；Negative Binomial/高方差模型未晋升。
- Calibration 只诊断，不修改正式概率。
- GPT 永远 `EXPLANATION_ONLY`。

## 半全场分时采集
Action 可 best-effort 补充：
`0-15 / 16-30 / 31-45 / 46-60 / 61-75 / 76-90`
的进球/失球结构。优先 SoccerSTATS，其次 InPlayWise；使用本地 Action cache，失败自动退回冻结 Conditional HTFT，不阻断主预测。

## 正式输出
固定 6 列：
`球队对阵 | 胜平负场景 | 市场概率 | 比分×2及概率 | 半全场×2及概率 | 总进球及概率`

不再正式显示：置信等级、置信度、最终筛选。

## 数据保护
- 已结束比赛的半场/全场比分只能作为标签，不能作为赛前输入。
- 禁止使用“建议下注”“是否下注”。
- 不使用 10013 / 10016 / 10017 / xi.php 作为正式基础源。
- 不建长期数据库。
- 2026-05-01 至 2026-09-20 是开发数据，不再作为 untouched final validation。
- 任何后续阈值/Challenger 晋升仍需冻结后的 Shadow / Forward 验证。
