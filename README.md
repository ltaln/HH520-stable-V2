# HH520 Stable V3.4

## 目标

Stable V3.4 将 10027S 反推研究正式整理成一条可解释、可验证的预测链：

**赔率负责基础概率；基本面负责识别市场失败；FT 决定 HT/FT；HT/FT 决定比分。**

正式基础数据源仍固定为 HH520 `10027s.php`，GitHub Actions、ChatGPT 一句命令入口和 6 列输出保持兼容。

## 用户命令

`预测 YYYY-MM-DD 全部比赛`

## V3.4 完整架构

```text
ChatGPT / GitHub Actions
        ↓
HH520 10027S
        ↓
Parser + Data Quality Gate
        ↓
Market De-vig
        ↓
┌──────────────────────────────┐
│ Draw Layer                   │
│ PD_anchor =                  │
│ 0.789×PD_market +            │
│ 0.211×25.74%                 │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│ Side Layer                   │
│ HomeShare =                  │
│ (1/OH)/[(1/OH)+(1/OA)]       │
└──────────────┬───────────────┘
               ↓
Base FT Probability H/D/A
               ↓
Market Failure Detector
               ↓
CONFIRM / BALANCED / TAIL_ALERT / PASS
               ↓
Value Layer（只判断价值，不改方向）
               ↓
FT-conditioned HT/FT Layer
               ↓
HT/FT-conditioned Score Layer
               ↓
Cross-layer Consistency
               ↓
6列正式输出
               ↓
GPT EXPLANATION_ONLY
```

## Probability Layer

### 1. 官方赔率去水

```text
qi = 1 / oddsi
Pi = qi / Σq
```

该值继续作为“市场概率”。

### 2. Draw Anchor

平局不再和主客一起重新计算，而是以市场平局概率为锚做轻微均值回归：

```text
PD_anchor =
0.789 × PD_market
+ 0.211 × 25.74%
```

这些系数来自开发样本反推，不宣称是 HH520 源代码中的精确常数；后续仍需 forward/shadow 验证。

### 3. Side Layer

```text
HomeShare =
(1/OH) / [(1/OH)+(1/OA)]

SidePool = 1 - PD_anchor

PH = SidePool × HomeShare
PA = SidePool × (1-HomeShare)
PD = PD_anchor
```

10027S 的“融合真实概率”只保留为研究/诊断字段，不再覆盖正式 FT 方向。

## Market Failure Detector

五项基本面不再线性修改 H/D/A，而只判断市场方向是否可靠。

以市场主客优势方为统一视角：

```text
防守差 <= -0.5                         +3
进攻差 <= -2 且 交锋差 >= +3          +2
Pfav < 60% 且 状态差 >= +0.5          +2
Pfav < 55% 且 交锋差 >= +3            +2
控球差 <= -8%                          +1

Pfav >= 65%                            -2
60% <= Pfav < 65%                      -1
```

分级：

```text
RiskScore <= 0  → CONFIRM
RiskScore = 1   → BALANCED
RiskScore 2~4   → TAIL_ALERT
RiskScore >= 5  → PASS
```

注意：PASS 表示“不作为强推荐”，不是删除比赛；预测链仍可输出结构结果。

## HT/FT Layer

半全场不再独立预测，而由 FT 条件生成。

主胜：
- 强方向：胜/胜 → 平/胜
- 较弱方向：平/胜 → 胜/胜

客胜：
- 强方向：负/负 → 平/负
- 较弱方向：平/负 → 负/负

平局：
- 第一候选：平/平
- 第二候选：根据 HomeShare 选择 胜/平 或 负/平

开发样本中，优势方最终赢球时，“半场优势方领先 + 半场平”覆盖绝大多数，半场落后后逆转只占很小比例。

V3.4 正式链不再依赖外部分时数据；10027S 是唯一正式基础源。

## Score Layer

V3.3 的 `POOLED_POISSON` 从正式生产链移出。V3.4 使用 HT/FT 条件比分模板：

```text
胜/胜 → 2:1 / 2:0
平/胜 → 2:1 / 1:0
负/负 → 1:3 / 0:2
平/负 → 0:1 / 1:2
平/平 → 0:0 / 1:1
胜/平 → 1:1 / 2:2
负/平 → 1:1 / 2:2
```

比分概率是“在当前 HT/FT 条件链中的模板概率”，不能解释成 FT 命中率。

## Value Layer

Value Layer 保留，但职责严格限定为：

- 比较市场与独立价值字段；
- 输出 EV / Kelly / value diagnostics；
- **不得修改 FT 方向**；
- **不得因为有价值就推导某队更可能获胜**。

页面“建议下注 / 是否下注”仍禁止进入正式决策。

## Confidence / Probability 语义

V3.4 明确区分：

- **市场概率**：官方赔率去水概率；
- **模型概率**：Draw Anchor + Side Layer 后的 H/D/A；
- **Risk Tier**：CONFIRM / BALANCED / TAIL_ALERT / PASS；
- **HT/FT概率**：条件链中的联合概率；
- **比分概率**：HT/FT 模板生成的条件概率。

禁止把这些字段统一叫成一个模糊“自信度”。

## 正式输出

保持 6 列：

`球队对阵 | 胜平负场景 | 市场概率 | 比分×2及概率 | 半全场×2及概率 | 总进球及概率`

胜平负场景会附带可靠度，例如：

- 主胜（确认）
- 客胜（尾部预警）
- 主胜（回避）

## 与 V3.3 的主要变化

- 保留：10027S、市场去水、GitHub Actions、GPT解释层、6列输出。
- 替换：纯市场 WDL → Draw Anchor + Side Layer。
- 替换：State/Conflict 主决策 → Market Failure Detector。
- 替换：Conditional HTFT 矩阵 → FT 条件模板。
- 替换：Pooled Poisson → HT/FT 条件比分模板。
- 降级：10027S 融合概率只作诊断。
- 移除正式依赖：外部 goal-timing 数据。
- 不变：Value 不决定方向；GPT 永远 EXPLANATION_ONLY。

## 研究验证边界

2026-09-10 至 2026-09-20 用于本轮候选规则开发，因此不是 untouched final validation。

当前研究观察到 Failure Detector 能把高可靠与低可靠场次明显分离，但这些数字不能视为未来准确率保证。V3.4 上线后应继续使用未来比赛做 Shadow / Forward 验证，任何阈值调整先进入 Candidate，不自动修改 Stable。

## 数据保护

- 已结束比赛的半场/全场比分只能作为研究标签，不能作为赛前输入。
- 禁止正式使用“建议下注 / 是否下注”。
- 不使用 10013 / 10016 / 10017 / xi.php 作为正式基础源。
- 不建长期数据库。
- GPT 不得修改锁定预测结果。
