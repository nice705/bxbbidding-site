# 标讯宝 — Bidding Site

全国全行业招标采购信息聚合平台。源头信息，完全免费。

## 架构

```
项目根目录
├── index.html              # 首页 → 调 /api/bids
├── list.html               # 标讯列表 → 调 /api/bids?q=&industry=&page=
├── detail.html             # 标讯详情 → 调 /api/bids/:id
├── static/
│   └── wxpusher-qr.svg     # 微信关注二维码（部署前替换为真实二维码）
├── data/bids.json          # 数据源（爬虫写入，不对外暴露）
├── functions/
│   └── api/
│       ├── _wxpusher.js          # WxPusher 推送工具库
│       ├── bids.js               # 列表 API（Cloudflare Pages Function）
│       ├── bids/[id].js          # 详情 API（Cloudflare Pages Function）
│       ├── subscribe/stats.js    # 订阅统计 API
│       └── cron/push.js          # 每日推送接口（供 Cron Trigger 调用）
├── robots.txt              # 禁止爬虫
├── _headers                # 安全响应头
├── wrangler.toml           # Pages 部署配置
└── README.md               # 本文件
```

## 防护体系

| 层 | 措施 | 挡谁 |
|---|---|---|
| HTTP 层 | Cloudflare WAF + Bot Fight Mode | 脚本、爬虫 |
| API 层 | Referer 校验（仅本站可调） | curl/wget 直接调用 |
| API 层 | 频率限制（60次/分） | 批量抓取 |
| 数据层 | 列表不返回 content 字段 | 全量数据窃取 |
| 展示层 | robots.txt Disallow 全部 | 搜索引擎索引 |
| 法律层 | 版权声明 + 服务条款 | 法律追责依据 |

## 微信推送订阅（WxPusher）

### 用户流程

```
用户首次访问标讯宝
├─ 3 秒后右下角自动弹出订阅弹窗
│  ┌──────────────────────┐
│  │     [微信二维码]      │
│  │   📢 免费订阅每日标讯  │
│  │  微信扫码关注          │
│  │  每天推送最新标讯      │
│  └──────────────────────┘
│
├─ 用户扫码 → 关注 WxPusher 公众号
│  → 自动订阅，无需任何操作
│  → 关闭弹窗，继续浏览
│
└─ 每天收到微信推送：
   📢 标讯宝 · 5月24日 星期四
   ━━━━━━━━━━━━━━━━━━
   今日更新 46 条标讯
   
   ▸ 医疗设备（12条）
     · 中山大学附属第一医院 CT设备采购 ¥2,800万
     · 四川省人民医院 3.0T核磁共振 ¥1,950万
     ...
   
   ▸ IT信息化（8条）
     · 上海市政务云平台扩容 ¥4,500万
     ...
   
   ━━━━━━━━━━━━━━━━━━
   ↗ 查看全部标讯
```

### 配置步骤

```
1. 注册 WxPusher
   → 打开 wxpusher.zjiecode.com
   → 微信扫码注册

2. 创建应用
   → 我的应用 → 创建应用
   → 应用名称：标讯宝
   → 应用描述：每日标讯推送
   → 回调地址：https://你的域名/api/subscribe/callback（可选）
   → 创建成功后得到 AppToken（格式：AT_xxxxxx）

3. 创建主题
   → 主题管理 → 创建主题
   → 主题名称：每日标讯
   → 创建成功后得到 topicId（数字）

4. 获取二维码
   → 主题详情 → 下载关注二维码
   → 替换 static/wxpusher-qr.svg 为下载的 PNG 图片
   → 或上传 png 后更新 HTML 中的图片路径

5. 设置环境变量（CF Dashboard）
   → Workers & Pages → 标讯宝 → 设置 → 环境变量
   ┌──────────────────────────┬──────────────────────────┐
   │ WXPUSHER_APP_TOKEN       │ AT_xxxxxx               │
   │ WXPUSHER_TOPIC_ID        │ 12345                   │
   │ SITE_URL                 │ https://你的域名         │
   │ CRON_AUTH_TOKEN          │ 你自己设的密码（可选）    │
   └──────────────────────────┴──────────────────────────┘
```

### 每日推送配置

两个方案任选其一：

**方案 A：Hermes cronjob（推荐）**
```bash
# 使用 Hermes 定时任务，每天早上 9 点推送
cronjob \
  action=create \
  schedule="0 9 * * *" \
  prompt="调用标讯宝推送接口：curl -X POST https://你的域名/api/cron/push -H 'X-Auth-Token: 你设的密码'"
```

**方案 B：Cloudflare Cron Trigger**
```
1. 创建一个单独的 Workers 脚本
2. 添加 Cron Trigger（每天 09:00 和 18:00）
3. 脚本内 fetch 标讯宝的 /api/cron/push
```

### 频次建议

```
每天 2 次：09:00 早间简报 + 18:00 下午更新
周末 1 次：09:00 周末汇总
勿过多推送，避免用户取消关注

弹窗频率：每天只自动弹 1 次（localStorage 控制）
             右下角浮动按钮随时可手动打开
```

## 部署

### Cloudflare Pages

1. 在 CF Dashboard → Workers & Pages → 创建 Pages 项目
2. 连接 GitHub 仓库，或直接上传项目目录
3. 构建配置：
   - **构建命令**：（空白，纯静态）
   - **输出目录**：`.`（项目根目录）
4. 绑定域名

> **不推荐**直接用 `npx wrangler pages deploy .` 部署到 Pages

### 部署后配置（CF Dashboard）

1. **设置 → 环境变量** → 添加 WxPusher 配置
2. **安全 → WAF** → 开启 **Bot Fight Mode**
3. **安全 → 速率限制** → 每 IP 每分钟 60 次
4. **SSL/TLS** → Full (strict)

## 数据更新

爬虫脚本写入 `data/bids.json` 后，重新部署到 Pages 即可生效。

推荐做法：
- 通过 GitHub Actions 定时运行爬虫
- 爬虫写入后自动 commit + push
- Pages 自动触发重新部署

## 本地开发

```bash
# 安装 Wrangler
npm install -g wrangler

# 本地预览（含 Pages Functions）
wrangler pages dev .

# 部署
wrangler pages deploy .
```
