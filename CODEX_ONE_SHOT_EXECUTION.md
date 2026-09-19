# Codex One-Shot Execution — HH520 Stable V2 V1.5

请在新仓库 `HH520-Stable-V2` 中完整实现本包规格。

必须：
1. 10023s 为唯一正式采集入口。
2. URL 固定：
   `https://www.hh520.com/tx/10023s.php?riqi=YYYY-MM-DD&threshold=1&bankroll=5000`
3. Firecrawl 只调用 `/v2/scrape`，默认只取 markdown。
4. 每个日期正式预测最多一次网络抓取；重复运行使用本地缓存。
5. 使用 basic proxy，除非实际证明失败；不得默认 stealth/auto。
6. 不使用 crawl。
7. 不接入10013/10016/10017/xi.php。
8. 正式预测不含旧回测系统。
9. 新增独立 `research/` 离线评估模块，但它不得自动修改 Stable。
10. EV/Kelly 保留字段，但不决定比赛方向。
11. Parser 必须依据真实10023s markdown建立字段映射；不得猜列。
12. 需要单元测试：URL builder、command router、market baseline、cache。
13. README 中说明手机/电脑一句命令：
    `预测 YYYY-MM-DD 全部比赛`
14. 不提交 `.env`、缓存、历史原始数据。

Firecrawl额度保护：
- scrape单页
- markdown only
- one request/date
- local cache first
- basic proxy first

完成后报告：
- 新增/修改文件
- 测试结果
- 10023s真实解析尚需的样本字段
- 不要增加未要求功能
