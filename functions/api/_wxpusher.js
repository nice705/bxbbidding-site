/**
 * WxPusher 消息推送工具库
 *
 * 使用前需要在 WxPusher 后台（wxpusher.zjiecode.com）:
 *   1. 注册账号 → 创建应用 → 获取 AppToken
 *   2. 创建主题 → 获取 topicId
 *   3. 下载关注二维码 → 放到项目根目录 static/wxpusher-qr.png
 *
 * 环境变量（在 Cloudflare Dashboard → Pages → 标讯宝 → 环境变量 中设置）:
 *   WXPUSHER_APP_TOKEN = AT_xxxxxx
 *   WXPUSHER_TOPIC_ID  = 12345
 *   SITE_URL           = https://你的域名
 */

const WXPUSHER_API = 'https://wxpusher.zjiecode.com/api'

/**
 * 发送微信推送
 *
 * @param {object} env - Pages Functions 的 context.env
 * @param {string} content - 推送内容（支持纯文本或 Markdown）
 * @param {number} contentType - 1=纯文本, 3=Markdown
 * @param {string} url - 点击消息后的跳转链接（可选）
 * @returns {object} { success, message, data }
 */
export async function sendWxPush(env, content, contentType = 1, url = '') {
  const appToken = env.WXPUSHER_APP_TOKEN
  const topicId = parseInt(env.WXPUSHER_TOPIC_ID || '0')
  const siteUrl = env.SITE_URL || 'https://bidding-site.pages.dev'

  if (!appToken || !topicId) {
    return { success: false, message: 'WxPusher 未配置（缺少 AppToken 或 TopicId）' }
  }

  const payload = {
    appToken,
    content,
    contentType,
    topicIds: [topicId],
    url: url || siteUrl + '/list.html',
  }

  try {
    const resp = await fetch(WXPUSHER_API + '/send/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = await resp.json()

    if (data.code === 1000) {
      return { success: true, message: `推送成功（${data.data?.count || 0} 人收到）`, data }
    }
    return { success: false, message: `WxPusher 错误：${data.msg || '未知错误'}`, data }
  } catch (err) {
    return { success: false, message: `请求失败：${err.message}` }
  }
}

/**
 * 查询应用关注者数量
 */
export async function getFollowerCount(env) {
  const appToken = env.WXPUSHER_APP_TOKEN
  if (!appToken) return 0

  try {
    const resp = await fetch(`${WXPUSHER_API}/fun/queryUserCount?appToken=${appToken}`)
    const data = await resp.json()
    return data.data?.count || 0
  } catch {
    return 0
  }
}

/**
 * 生成标准化的每日标讯推送内容
 *
 * @param {Array} bids - 标讯数组
 * @param {number} todayCount - 今日更新总数
 * @returns {string} 格式化后的推送文本
 */
export function formatDailyDigest(bids, todayCount) {
  const date = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
  })

  let text = `📢 标讯宝 · ${date}\n━━━━━━━━━━━━━━━━━━\n`

  if (todayCount > 0) {
    text += `今日更新 ${todayCount} 条标讯，按行业分类如下：\n\n`
  } else {
    text += '今日暂无新增标讯\n\n'
    return text
  }

  // 按行业分组
  const groups = {}
  for (const bid of bids) {
    const ind = bid.industry || '其他'
    if (!groups[ind]) groups[ind] = []
    if (groups[ind].length < 5) groups[ind].push(bid) // 每个行业最多5条
  }

  for (const [industry, items] of Object.entries(groups)) {
    text += `▸ ${industry}（${items.length}条）\n`
    for (const b of items) {
      const title = b.title.length > 28 ? b.title.slice(0, 28) + '…' : b.title
      text += `  · ${title}  ${b.budget || ''}\n`
    }
    text += '\n'
  }

  text += '━━━━━━━━━━━━━━━━━━\n'
  text += '↗ 查看全部标讯'

  return text
}
