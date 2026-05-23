/**
 * 标讯宝 API — 详情接口
 * GET /api/bids/:id
 *
 * 返回单条标讯完整数据（含 content 全文）
 *
 * 防护:
 *   - 请求频率限制
 *   - Referer 校验
 *   - 只返回匹配 id 的单条数据
 */

const rateLimitMap = new Map()
const RATE_LIMIT_WINDOW = 60_000
const RATE_LIMIT_MAX = 120 // 详情页访问更频繁，放宽到 120次/分钟

function getClientIP(request) {
  return request.headers.get('cf-connecting-ip')
      || request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
      || 'unknown'
}

function checkRateLimit(ip) {
  const now = Date.now()
  const entry = rateLimitMap.get(ip)
  if (!entry || now - entry.windowStart > RATE_LIMIT_WINDOW) {
    rateLimitMap.set(ip, { windowStart: now, count: 1 })
    return true
  }
  if (entry.count >= RATE_LIMIT_MAX) return false
  entry.count++
  return true
}

function validateReferer(request, siteDomain) {
  const referer = request.headers.get('Referer') || ''
  if (!referer) return false
  try {
    const refUrl = new URL(referer)
    if (refUrl.hostname === siteDomain) return true
    if (refUrl.hostname === 'localhost' || refUrl.hostname === '127.0.0.1') return true
    if (refUrl.hostname.endsWith('.pages.dev')) return true
    return false
  } catch {
    return false
  }
}

export async function onRequest(context) {
  const { request, env, params } = context
  const url = new URL(request.url)
  const siteDomain = url.hostname
  const bidId = params.id

  if (!bidId) {
    return new Response(JSON.stringify({ error: '缺少标讯 ID', code: 'MISSING_ID' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    })
  }

  // 1. Referer 校验
  if (siteDomain !== 'localhost' && siteDomain !== '127.0.0.1') {
    if (!validateReferer(request, siteDomain)) {
      return new Response(JSON.stringify({ error: '禁止直接访问', code: 'ACCESS_DENIED' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      })
    }
  }

  // 2. 频率限制
  const clientIP = getClientIP(request)
  if (!checkRateLimit(clientIP)) {
    return new Response(JSON.stringify({ error: '请求过于频繁', code: 'RATE_LIMITED' }), {
      status: 429,
      headers: { 'Content-Type': 'application/json', 'Retry-After': '60' }
    })
  }

  // 3. 读取数据
  try {
    const assetUrl = new URL('/data/bids.json', request.url)
    const assetResponse = await env.ASSETS.fetch(assetUrl)

    if (!assetResponse.ok) {
      return new Response(JSON.stringify({ error: '数据源不可用', code: 'DATA_UNAVAILABLE' }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    const data = await assetResponse.json()
    const bids = data.bids || []

    // 4. 查找 id
    const bid = bids.find(b => b.id === bidId)

    if (!bid) {
      return new Response(JSON.stringify({ error: '未找到该标讯', code: 'NOT_FOUND' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    // 5. 返回完整数据
    return new Response(JSON.stringify({
      bid: bid,
      todayCount: data.todayCount,
      updatedAt: data.updatedAt,
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=300, s-maxage=600',
        'X-Robots-Tag': 'noindex',
      }
    })

  } catch (err) {
    return new Response(JSON.stringify({ error: '服务器内部错误', code: 'INTERNAL_ERROR' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}
