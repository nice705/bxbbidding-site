/**
 * 每日标讯推送（Cron Trigger 入口）
 * POST /api/cron/push
 *
 * 触发方式：
 *   方案A：Cloudflare Cron Trigger
 *     - 创建一个 Workers 脚本作为定时触发器
 *     - 每天 09:00 和 18:00 调用此路由
 *
 *   方案B：Hermes cronjob（推荐，运维更可控）
 *     - 使用 cronjob 工具创建定时任务
 *     - 每天定时 curl 此端点
 *
 * 逻辑：
 *   1. 读取 data/bids.json 的最新标讯
 *   2. 按行业分类整理成每日简报
 *   3. 调用 WxPusher API 推送给所有关注者
 *
 * 安全：通过 X-Auth-Token 鉴权，防止被随意调用
 */

import { sendWxPush, formatDailyDigest } from '../_wxpusher.js'

export async function onRequest(context) {
  const { request, env } = context

  // 仅允许 POST
  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ error: '请使用 POST 方法' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    })
  }

  // 鉴权（防止被随意调用）
  const authHeader = request.headers.get('X-Auth-Token') || ''
  const expectedToken = env.CRON_AUTH_TOKEN || ''
  if (expectedToken && authHeader !== expectedToken) {
    return new Response(JSON.stringify({ error: '鉴权失败' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' }
    })
  }

  try {
    // 1. 读取标讯数据
    const assetUrl = new URL('/data/bids.json', request.url)
    const assetResp = await env.ASSETS.fetch(assetUrl)

    if (!assetResp.ok) {
      return new Response(JSON.stringify({
        success: false,
        message: '数据源不可用'
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    const data = await assetResp.json()
    const bids = data.bids || []
    const todayCount = data.todayCount || 0

    // 2. 格式化推送内容
    const content = formatDailyDigest(bids, todayCount)

    // 3. 发送推送
    const result = await sendWxPush(env, content, 1, env.SITE_URL + '/list.html')

    return new Response(JSON.stringify({
      success: result.success,
      message: result.message,
      stats: {
        todayCount,
        totalBids: bids.length,
      }
    }), {
      status: result.success ? 200 : 500,
      headers: { 'Content-Type': 'application/json' }
    })

  } catch (err) {
    return new Response(JSON.stringify({
      success: false,
      message: `推送失败：${err.message}`,
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}
