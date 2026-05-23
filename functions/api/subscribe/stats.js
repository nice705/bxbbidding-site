/**
 * 订阅统计接口
 * GET /api/subscribe/stats — 返回关注者数量
 *
 * 环境变量：WXPUSHER_APP_TOKEN
 */

import { getFollowerCount } from './_wxpusher.js'

export async function onRequest(context) {
  const { request, env } = context

  // 仅允许 GET
  if (request.method !== 'GET') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json' }
    })
  }

  const count = await getFollowerCount(env)
  const hasToken = !!env.WXPUSHER_APP_TOKEN
  const hasTopicId = !!env.WXPUSHER_TOPIC_ID

  return new Response(JSON.stringify({
    followerCount: count,
    configured: hasToken && hasTopicId,
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300',
    }
  })
}
