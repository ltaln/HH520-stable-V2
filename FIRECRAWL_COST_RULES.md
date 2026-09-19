# Firecrawl Cost Rules

依据 Firecrawl 当前文档：
- 单 URL 使用 scrape。
- `formats=["markdown"]` 即可。
- `onlyMainContent=true`。
- `maxAge` 可用于服务端缓存提速，但缓存结果仍可能计 credit，因此本项目以本地日期缓存节省额度。
- `basic` proxy 优先；`stealth` / `auto` 可能增加 credit。
- 禁止 crawl 整站。
- 正式预测每日期最多一次 Firecrawl 网络调用。

月额度1000时，30天每日一次理论网络抓取约30次，留有大量余量。
