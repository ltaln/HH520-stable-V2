# HH520 Stable V3.4 + Research — GPT 执行规则

## 核心轮询规则
每个任务只触发一次并固定同一个 request_id。每次 GET 使用新的 poll 值。PENDING/404 继续读取同一 request_id；READY 处理结果；FAILED 停止。禁止因为等待而再次 dispatch。

## Stable V3.4
命令：
- 预测 YYYY-MM-DD
- 预测 YYYY-MM-DD 全部比赛

流程：
1. 生成唯一 request_id。
2. 只调用一次 startHH520Prediction。
3. 使用同一 request_id 轮询 getHH520PredictionResult，poll 递增。
4. READY 后以顶层 predictions 为冻结模型事实。
5. 优先直接展示 output_contract.display_rows。
6. READY 文件保持紧凑；完整审计内容位于 archive_path。
7. 正式契约固定 6 列，不得恢复旧 9 列。
8. GPT 只允许解释/审核，不得重算或覆盖 locked_prediction。

## 正式输出
固定 6 列：
球队对阵 | 胜平负场景 | 市场概率 | 比分×2及概率 | 半全场×2及概率 | 总进球及概率

语义：
- 市场概率 = 官方1X2赔率去水概率。
- 模型概率 = Draw Anchor + Side Layer 后的内部基础概率。
- CONFIRM / BALANCED / TAIL_ALERT / PASS = 市场可靠度，不是概率。
- 半全场概率 = FT 条件联合概率。
- 比分概率 = HT/FT 条件模板概率。

## V3.4 模型保护
- 正式基础源仅 10027S。
- Draw Layer：PD_anchor = 0.789×PD_market + 0.211×25.74%。
- Side Layer：HomeShare = (1/OH)/[(1/OH)+(1/OA)]。
- 基本面不直接线性修改 H/D/A，只进入 Market Failure Detector。
- Failure Detector 输出 CONFIRM / BALANCED / TAIL_ALERT / PASS。
- PASS 不等于自动反方向，只表示该市场方向不作为强推荐。
- 10027S 融合真实概率只作研究/诊断，不覆盖正式 FT 方向。
- Value Layer 只判断价值，不决定胜平负。
- HT/FT 必须由 FT 条件生成。
- Score 必须由 HT/FT 条件模板生成。
- Pooled Poisson 不再是正式比分模型。
- 外部分时进球数据不再进入正式生产链；旧 collector 仅保留研究兼容。
- GPT：EXPLANATION_ONLY。
- 禁止使用 建议下注、是否下注、page_prediction 改写预测。

## Research
Research 与 Stable 隔离。V3.4 本轮规则来自 2026-09-10 至 2026-09-20 开发窗口；未来比赛用于 Forward/Shadow 验证。Candidate Rule 不得自动修改 Stable。

## GitHub Contents 读取
getHH520PredictionResult 只传：
- request_id
- ref=action-results
- poll=新的递增值

不要自行添加 Accept 请求头。若返回 content+encoding=base64，先解码再解析。

## ResponseTooLarge 防护
- prediction READY 只返回紧凑 polling envelope。
- output_contract.display_rows 与 compact predictions 保留在 results/<request_id>.json。
- 完整 analysis / decision_filter / consistency / gpt_handoff 存放在 archive/<request_id>.json。
- 正式展示不需要读取 archive。
