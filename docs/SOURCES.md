# 实现依据

- 原始用户提供包：HH520_Stable_V2_Full_Execution_Package_V1_5.zip。
- 真实字段样本：2026-09-19 固定10023s URL，Firecrawl scrapeId 01a0b9e7-815a-75ef-a560-2e1622eea657，basic，HTTP 200，creditsUsed=1。基础27场，融合13场，存在重复展示。原始响应仅存本地缓存，不纳入发行包。
- OpenAI结构化输出接口：https://developers.openai.com/api/docs/guides/structured-outputs
- 真实采集验证使用已安装Firecrawl连接器；本地requests客户端以mock核对请求参数，没有第二次抓取。

原包执行文档按项目需求审查实施；其中创建GitHub仓库、手机ChatGPT自动执行的步骤并不能由本地代码自动完成。
