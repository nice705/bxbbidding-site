==============================================
标讯宝 (qgbxb.com) 防丢版备份
==============================================
版本: 线上生产版 (CF Pages fdb725b4)
备份时间: 2026-06-09 03:29:16
来源: /tmp/bidding-site/ (GitHub nice705/bxbbidding-site)

【版本说明】
- 当前 qgbxb.com 运行版本 (已回滚至 fdb725b4)
- 部署时间: 2026-06-07 22:00 (北京时间)
- API功能: 方法筛选/正文清洗/去噪/收藏/订阅
- 数据量: 31,799条标讯

【目录结构】
- 页面: index.html / list.html / detail.html / favorites.html / subscribe.html / coming-soon.html
- API: functions/api/ (bids.js / _data.js / bids/[id].js)
- 数据: data/ (bids-homepage.json / bids.json.gz / customers.json / customer_history.json)
- 脚本: scripts/ (爬虫/工具/部署)
- 配置: _headers / _routes.json / manifest.json / robots.txt / .cfignore
- CI: .github/workflows/deploy.yml
- 静态: static/ (holiday-utils.js / wxpusher-qr.svg)
- SEO: sitemap.xml (1186万条)

最近 commit:
492acb4 fix: 去掉accountId参数，让wrangler自动检测Cloudflare账号
46c88a2 更新数据: 6333条标讯 + 新增数据源 + 爬虫重构
c998c56 Trigger deploy via GitHub Actions
8459265 更新数据: 5394条标讯
5d18773 feat: 列表页卡片布局与首页一致 - 潜在渠道商/供应商按钮
b594dd5 feat: 底部改为网站功能介绍
e068a78 fix: 按钮改用onclick跳转，避免a嵌套a
6c1ad73 feat: 潜在渠道商/供应商按钮可点击，跳转敬请期待页
bb1c96c feat: remove source platform display from bid cards
1c1c530 fix: move bottom nav before CF injection point to prevent it from being pushed outside body
cd0f358 fix: remove CF injected </div></body> that broke bottom nav
00fd642 fix: 桌面端去掉暗色模式 + 首页自动弹订阅窗 + 详情页CF注入修复
f05747c fix: show bid content directly instead of blocked message
8275832 fix: restore 31k bids data + fix API to return 'items' format matching HTML expectations
f38e0cb feat: add favorites.html page + favorites link in all bottom navs
7c1a859 fix: remove line numbers from HTML files, add bottom nav
e7c7c3f fix: add bottom nav to index.html
e67b382 fix: add missing API route handlers (_routes.json, /api/bids, /api/bids/[id])
2316695 fix: list from GitHub Raw
90678b9 fix: index from GitHub Raw
6b535fc fix: 首页从 GitHub Raw 加载数据
f9f651f fix: 详情页添加数据源fallback和字段兼容
c64269b chore: 添加 .cfignore 排除大文件
ff14c7e fix: 精简到500条修复详情页
0acc583 fix: 精简 bids.json 修复详情页加载
f8bef35 fix: 重新部署 bids.json - 修复详情页数据加载失败
08827d5 fix: 清洗数据 - 删除被屏蔽内容和重复数据
d9e8771 fix: 数据文件 gzip 压缩绕过 CF Pages 25MB 限制
9a6cb99 refactor: 订阅页简化 - 分组tab切换, 单栏布局, 去掉热门建议
d2f91d2 feat: 关键词订阅支持分组管理，列表页按分组选择关键词

【文件清单】
./.cfignore
./.cfignore.local.bak
./.github/workflows/deploy.yml
./.gitignore
./README.md
./_headers
./_routes.json
./check_count.sh
./coming-soon.html
./data/bids-homepage.json
./data/bids.json
./data/bids.json.gz
./data/customer_history.json
./data/customers.json
./detail.html
./ensure_historical.sh
./favorites.html
./functions/api/_data.js
./functions/api/bids.js
./functions/api/bids/[id].js
./functions/data/bids.json.js
./index.html
./index.html.bak
./index.html.bak2
./list.html
./manifest.json
./robots.txt
./scripts/analyze_blocked.py
./scripts/append_bigdata.py
./scripts/append_crm.py
./scripts/append_entity_db.py
./scripts/archive/deleted_spiders/ggzy_spider.py
./scripts/archive/deleted_spiders/province_config.py
./scripts/archive/deleted_spiders/province_deep_spider.py
./scripts/archive/deleted_spiders/spider_base.py
./scripts/archive/deleted_spiders/spider_ccgp.py
./scripts/archive/deleted_spiders/spider_cebpub.py
./scripts/archive/deleted_spiders/spider_cebpub_historical.py
./scripts/archive/deleted_spiders/spider_cebpub_playwright.py
./scripts/archive/deleted_spiders/spider_chinabidding.py
./scripts/archive/deleted_spiders/spider_cnooc.py
./scripts/archive/deleted_spiders/spider_gdggzy.py
./scripts/archive/deleted_spiders/spider_operators.py
./scripts/archive/deleted_spiders/spider_plap.py
./scripts/archive/deleted_spiders/spider_provinces.py
./scripts/archive/deleted_spiders/spider_proxy.py
./scripts/archive/deleted_spiders/spider_sgcc.py
./scripts/archive/deleted_spiders/unified_spider.py
./scripts/backfill_fields.py
./scripts/build-sitemap.py
./scripts/cebpub_bulk.sh
./scripts/cebpub_daily.sh
./scripts/daily_update.sh
./scripts/deploy-prep.py
./scripts/expand-data.py
./scripts/export_sqlite_content.py
./scripts/product_extractor.py
./scripts/spider_base.py.bak-1657
./scripts/spider_ccgp.py.bak
./scripts/spider_cebpub_bulk.py
./scripts/spider_cebpub_historical.py.bak
./scripts/update_timestamp.py
./sitemap.xml
./spider_daily.sh
./spider_historical.sh
./spider_hourly.sh
./static/holiday-utils.js
./static/wxpusher-qr.svg
./subscribe.html
==============================================
