# V1.5运行与接入

原始README、GPT_INTEGRATION、预测Prompt及配置均保留。这里仅记录已实现代码的操作方式。

## 本地采集和模型输入

在项目目录执行：

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m pytest -q
py -3 main.py "预测 2026-09-19 全部比赛" --output reports/input.json
```

.env保存Firecrawl key，环境变量优先。运行时加载本项目的.env，不寻找其他目录的密钥。
未加--gpt时，程序输出READY_FOR_GPT及gpt_handoff；这是模型输入，不是最终预测。
gpt_handoff包含原Prompt、config和结构化分析，缺少网页现成比分不会阻止GPT推理。

可选程序侧模型调用：

```powershell
py -3 main.py "预测 2026-09-19 全部比赛" --gpt --output reports/prediction.json
```

该路径需要OPENAI_API_KEY、账户可用的OPENAI_MODEL。没有指定模型时不会擅自选择或调用。
GPT批量结果按模型、Prompt、配置和输入哈希缓存。保持原概率方向；比分/半全场/总进球冲突则PASS。
置信度按原confidence函数约束，不额外添加60%上限。

## 手机/电脑ChatGPT一句命令

正式目标仍是原包的ChatGPT对话入口，不再把之前新增的局域网页面当作完成品。
integration目录与controller/chatgpt_action.py是实现此要求的接入材料，不引入新的比赛模型。

1. 将项目部署到你指定的GitHub仓库对应的服务环境；GitHub保存代码本身不运行采集。
2. WSGI应用入口为controller.chatgpt_action:application。部署单进程、持久cache存储、HTTPS:443及有效证书。
3. 部署环境设置FIRECRAWL_API_KEY和独立HH520_ACCESS_TOKEN。服务端不需要OPENAI_MODEL/OpenAI key；ChatGPT负责最终推理。
4. 替换integration/chatgpt-action.openapi.json的servers占位URL。
5. 在你的自定义GPT配置中加载原Prompt和integration/CHATGPT_INSTRUCTIONS.md的执行约定，导入Action schema并配置Bearer认证。
6. 在手机/电脑同一个GPT中发送“预测 YYYY-MM-DD 全部比赛”。验收必须包含一次真实端到端命令。

API：POST /prepare提交命令；GET /prepared/YYYY-MM-DD?offset=0读取状态。
数据准备异步执行，避免等待采集时超出Action时限；每页最多10场，next_offset非空继续获取。
所有分页只读同次数据，不增加Firecrawl抓取。
服务重启后可重新prepare，已有日期仍使用磁盘缓存。多进程/多实例会破坏内存任务路由，当前不支持此部署方式。

开发检查可以运行“py -3 -m controller.chatgpt_action”；它仅监听127.0.0.1，不能直接给ChatGPT使用。
本次未启动后台服务、未修改防火墙、未发布公网地址或创建自定义GPT。

## 成本和限制

每日期最多一次网络抓取，失败/解析错误不自动重试；先保存raw再解析。
此前使用过的9月18、19、20日缓存继续复用。9月20日当次页面为空，快照不会自动更新。
缺密钥、坏缓存、结构变化会明确报错。空赛程只有来源页面明确表示无数据时才返回0场。
不要删除requested账本或通过新副本反复抓同一日期。
已出现比分的场次跳过，避免把赛果作为赛前预测。

## 当前外部待办

GitHub仓库已指定为https://github.com/ltaln/HH520-stable-V2 。尚无HTTPS部署环境或用户自定义GPT配置权限。
这些信息无法从原包推导，不能伪称已完成手机/电脑端到端上线。
若使用ChatGPT入口，不必为程序侧模型另外配置OPENAI_MODEL。

官方接口要求：https://developers.openai.com/api/docs/actions/production
