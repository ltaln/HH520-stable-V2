# HH520 Stable V3.3 Candidate Research

更新时间：2026-09-22  
状态：RESEARCH_ONLY / CANDIDATE_ONLY  
Stable：不修改、不自动晋升

## 1. 研究目标

基于用户提出的 8 个问题与 V3.2 历史验证结果，研究下一版候选架构。核心目标不是“为了反市场而反市场”，而是给市场基线增加结构识别、冲突保险、尾部场景、半全场数据补强和比分尾部研究能力。

开发数据：
- 2026-05-01 至 2026-09-20
- 合计 1,432 场
- 9月1日至20日已多次参与开发，只能作为 development stress，不能作为最终 untouched validation

## 2. 新发现：page_probability_concentration 是独立信号

Research Lab 里的 `probability_concentration` 不是市场去水 pmax，而是 10027s 的 `page_probability` 三项概率中的最大值分桶。

这意味着它可以作为市场之外的独立保险/冲突信号，而不是重复市场概率。

分桶定义：
- <40%
- 40-49%
- 50-59%
- >=60%

## 3. 跨月稳定性复核

### 3.1 WDL 稳定正向区域

#### page_probability_concentration >=60%
跨 4 个月、n=149：
- 加权准确率：77.18%
- 同条件月基线：51.26%
- 平均提升：+25.92pp
- 各月提升均为正
- 最弱月份仍约 +14.2pp

结论：
- 这是下一版最值得保留的“独立确认信号”之一
- 但只能用于确认/降级，不能自动翻转市场方向

#### home_odds <1.50
跨 5 个月、n=280：
- 加权准确率：69.64%
- 同条件月基线：50.73%
- 平均提升：+18.91pp
- 5个月均为正向

#### pattern = 🔶风控赔率
跨 5 个月、n=195：
- 加权准确率：69.23%
- 同条件月基线：50.64%
- 平均提升：+18.59pp
- 5个月均为正向

#### away_odds <1.50
跨 3 个月、n=93：
- 加权准确率：77.42%
- 同条件月基线：49.65%
- 平均提升：+27.77pp
- 3个月均为强正向

#### structure = 强优
跨 3 个月、n=83：
- 加权准确率：77.11%
- 同条件月基线：49.60%
- 平均提升：+27.51pp
- 3个月均为强正向

### 3.2 WDL 稳定负向区域

#### page_probability_concentration <40%
跨 4 个月、n=161：
- 加权准确率：32.92%
- 同条件月基线：49.15%
- 平均下降：-16.23pp
- 4个月全部为明显负向

这是下一版最强的“冲突/不可信”信号之一。

#### risk = 中高
跨 4 个月、n=289：
- 加权准确率：35.29%
- 同条件月基线：49.22%
- 平均下降：-13.93pp
- 4个月均为明显负向

#### home_odds 2.20-2.99
跨 4 个月、n=254：
- 加权准确率：33.86%
- 同条件月基线：49.25%
- 平均下降：-15.39pp

#### away_odds 2.20-2.99
跨 4 个月、n=273：
- 加权准确率：34.07%
- 同条件月基线：49.14%
- 平均下降：-15.08pp

#### pattern = ⚡ 极端
跨 3 个月、n=108：
- 加权准确率：32.41%
- 同条件月基线：48.98%
- 平均下降：-16.57pp

#### home_odds 1.80-2.19
跨 4 个月、n=253：
- 加权准确率：38.74%
- 同条件月基线：49.28%
- 平均下降：-10.54pp

#### away_odds 1.80-2.19
跨 4 个月、n=161：
- 加权准确率：37.89%
- 同条件月基线：48.96%
- 平均下降：-11.07pp

### 3.3 Balanced 结论

`structure = 均衡` 跨 5 个月、n=675：
- 加权准确率：45.48%
- 同条件月基线：50.02%
- 平均下降：-4.54pp
- 五个月均未显示稳定优势

结论：
- Balanced/均衡必须降级处理
- 但不能自动改成“平局”
- 原 Draw-adjusted 模型已经验证过没有稳定提升，所以 Balanced 应进入场景分流，不应硬翻成 DRAW

## 4. HTFT 新结论

当前 Conditional HTFT 仍然是基准，不直接替换。

跨月信号显示：
- home_odds <1.50：HTFT Top2 跨5个月约 63.9%
- away_odds <1.50：HTFT Top2 跨3个月约 68.8%
- page_probability_concentration >=60%：HTFT Top2 跨4个月约 64.4%

说明：
- 强市场/强结构时，当前 HTFT 的方向一致性更可靠
- 弱市场/冲突结构时，当前固定 `P(HT|FT)` 的不足更加明显

V3.3 研究方向：
1. 继续保留 Conditional HTFT 作为基准
2. 增加 15 分钟进球/失球数据后，训练独立 P(HT)
3. 再比较：
   - Conditional baseline
   - Timing-aware HT model
   - Timing-aware HTFT joint model
4. 未补齐时间数据前，不晋升新的 HTFT 结构

## 5. Score / Total Goals 新结论

跨月因子对 score_top2 / goals 没有出现像 WDL 那样稳定、强一致的提升。

结论：
- 当前 Pooled Poisson 仍应作为基准
- 不能因为“想看到 3:1 / 4:1 / 3:4”就人为放大高比分
- 下一版只建立研究 Challenger，不替换生产基准

V3.3 Score Challenger：
- Negative Binomial / over-dispersion
- Poisson + high-total mixture
- 联赛/球队高方差状态
- 高比分定义：总进球>=5 或任一方>=3
- 评估：
  - Top1 / Top2 / Top3 / Top5
  - NLL
  - High-score Recall
  - High-score Precision

只有在 NLL 不恶化、且高比分召回稳定提升时才考虑晋升。

## 6. V3.3 候选核心：State Engine

不再把所有比赛直接压成一个 WDL 方向。

候选状态：

### CONFIRMED
典型证据：
- 市场 pmax 强
- page_probability_concentration >=60%
- home/away odds <1.50
- structure=强优
- pattern=🔶风控赔率

处理：
- 市场方向作为主场景
- HTFT/Score 优先保持主方向一致
- 不需要额外 Tail 提醒，除非其他强冲突出现

### BALANCED
典型证据：
- 市场 margin 很小
- structure=均衡
- 市场三项概率接近

处理：
- 不把 argmax 描述成强方向
- 保留主场景 + 次场景
- Draw 只能作为候选，不自动翻转为平局

### CONFLICT
典型证据：
- page_probability_concentration <40%
- risk=中高
- pattern=⚡极端
- 市场处在历史低可靠赔率区间
- 市场与 page_probability / 基本面方向明显冲突

处理：
- 市场方向降级
- 禁止输出“确定主胜/客胜”式表达
- 进入 Tail / Upset 检查

### TAIL_ALERT
只在 CONFLICT/BALANCED 中触发。

作用：
- 排出非市场第一方向的备选场景
- 不自动覆盖主方向
- 记录高赔/爆冷候选及概率依据

## 7. Market Conflict / Insurance Layer

下一版“保险机制”不采用硬翻转，而采用：
1. Market Anchor
2. Independent Confirmation
3. Conflict Detection
4. Scenario Split

保险层要回答的是：
- 市场强不强？
- 10027s 独立概率是否确认？
- 风险/极端结构是否反向？
- 赔率是否处于历史低可靠区？
- 是否应从单方向变成双场景/尾部场景？

不允许：
- 因为某一项冲突就直接翻转主客胜
- 用赛果反推阈值
- 用同一市场概率既当基准又当独立确认

## 8. Cross-layer Consistency

V3.3 研究要求：
- WDL 主场景
- HTFT 主场景
- Score 主场景
- Total Goals

必须做一致性审计。

但不做硬锁死：
- 强结构：优先同方向
- Balanced/Conflict：允许不同方向，但必须标为次场景或 Tail
- 不允许把“主胜 + 主/主 + 客/客”三个同级展示

## 9. 输出研究目标

未来正式展示候选结构：

球队对阵 | 胜平负场景 | 市场概率 | 比分×2及概率 | 半全场×2及概率 | 总进球及概率

删除：
- 置信等级
- 置信度
- 最终筛选

内部仍可保留状态：
- CONFIRMED
- BALANCED
- CONFLICT
- TAIL_ALERT

但不强制在用户主表显示。

## 10. V3.3 当前候选架构

```
10027s market + page_probability + factors
        ↓
Market Proportional De-vig
        ↓
State Engine
  ├─ CONFIRMED
  ├─ BALANCED
  ├─ CONFLICT
  └─ TAIL_ALERT
        ↓
Market Conflict / Insurance Layer
        ↓
Primary WDL Scenario + Alternate/Tail Scenario
        ↓
Conditional HTFT baseline
        ↓
Timing-aware HTFT challenger（待补分时数据）
        ↓
Pooled Poisson baseline
        ↓
High-variance Score challenger
        ↓
Cross-layer consistency audit
        ↓
Probability calibration
        ↓
Simplified output
```

## 11. 当前研究结论

### 可以进入 V3.3 Candidate
- State Engine
- page_probability concentration 独立确认
- Market Conflict insurance
- Balanced 降级但不自动 Draw
- Tail Alert 作为独立次场景
- 输出各预测项概率
- 跨层一致性审计

### 暂不晋升
- 自动 Draw override
- 自动反市场
- Tail 直接覆盖市场主方向
- Timing-aware HTFT（缺历史分时数据）
- Negative Binomial / 高比分模型（尚未完成完整 walk-forward）
- 任何自动 Stable promotion

## 12. 下一步验证门槛

V3.3 Candidate 在进入 Stable 前必须：
1. 用 2026-05-01 至 2026-09-20 做 walk-forward development
2. 冻结阈值
3. 用 2026-09-21 之后的新数据做 Shadow
4. 再做 Forward
5. 人工审核
6. 只有在 WDL 不劣于市场、HTFT/Score 有增量价值、Tail 不制造大量假阳性时才晋升

最终状态：CANDIDATE_ONLY
