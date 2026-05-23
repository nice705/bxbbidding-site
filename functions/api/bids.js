/**
 * 标讯宝 API — 列表接口
 * GET /api/bids
 *
 * 参数:
 *   q         - 搜索关键词
 *   industry  - 行业筛选
 *   source    - 来源筛选
 *   page      - 页码（默认 1）
 *   pageSize  - 每页条数（默认 20，最大 200）
 *
 *
 * 响应:
 *   { bids: [...], todayCount, totalResults, page, pageSize }
 *
 * 防护:
 *   - Referer 校验（仅允许本站域名）
 *   - 列表不返回 content 字段（仅详情接口返回）
 *   - 内置频率限制（内存 Map，单 Worker 有效）
 */

// 简单的内存频率限制（单实例有效）
const rateLimitMap = new Map()
const RATE_LIMIT_WINDOW = 60_000 // 1 分钟
const RATE_LIMIT_MAX = 60        // 每分钟 60 次

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

  if (entry.count >= RATE_LIMIT_MAX) {
    return false
  }

  entry.count++
  return true
}

function validateReferer(request, siteDomain) {
  const referer = request.headers.get('Referer') || ''
  // 无 Referer 的请求（直接 curl / 程序调用）一律拦截
  if (!referer) return false
  try {
    const refUrl = new URL(referer)
    // 允许本站域名和 localhost 开发环境
    if (refUrl.hostname === siteDomain) return true
    if (refUrl.hostname === 'localhost' || refUrl.hostname === '127.0.0.1') return true
    // 允许 Pages 开发域名
    if (refUrl.hostname.endsWith('.pages.dev')) return true
    return false
  } catch {
    return false
  }
}

function fuzzyMatch(text, query) {
  if (!text || !query) return false
  const lowerText = text.toLowerCase()
  // 空格分隔的多关键词匹配（全部命中才算）
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean)
  return terms.every(term => lowerText.includes(term))
}

export async function onRequest(context) {
  const { request, env } = context
  const url = new URL(request.url)
  const siteDomain = url.hostname

  // 1. Referer 校验（生产环境）
  // 只在非 dev 环境启用，方便本地测试
  if (siteDomain !== 'localhost' && siteDomain !== '127.0.0.1') {
    if (!validateReferer(request, siteDomain)) {
      return new Response(JSON.stringify({
        error: '禁止直接访问',
        code: 'ACCESS_DENIED'
      }), {
        status: 403,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        }
      })
    }
  }

  // 2. 频率限制
  const clientIP = getClientIP(request)
  if (!checkRateLimit(clientIP)) {
    return new Response(JSON.stringify({
      error: '请求过于频繁，请稍后再试',
      code: 'RATE_LIMITED'
    }), {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': '60',
      }
    })
  }

  // 3. 读取数据
  try {
    const assetUrl = new URL('/data/bids.json', request.url)
    const assetResponse = await env.ASSETS.fetch(assetUrl)

    if (!assetResponse.ok) {
      return new Response(JSON.stringify({
        error: '数据源不可用',
        code: 'DATA_UNAVAILABLE'
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    const data = await assetResponse.json()
    let bids = data.bids || []

    // 4. 过滤
    const q = url.searchParams.get('q') || ''
    const industry = url.searchParams.get('industry') || ''
    const source = url.searchParams.get('source') || ''

    if (q) {
      bids = bids.filter(b =>
        fuzzyMatch(b.title, q) ||
        fuzzyMatch(b.industry, q) ||
        fuzzyMatch(b.region, q)
      )
    }
    if (industry) {
      bids = bids.filter(b => b.industry === industry)
    }
    if (source) {
      bids = bids.filter(b => b.source === source)
    }

    // 5. 排序（按日期倒序）
    bids.sort((a, b) => new Date(b.date) - new Date(a.date))

    // 6. 分页
    const totalResults = bids.length
    const page = Math.max(1, parseInt(url.searchParams.get('page') || '1'))
    const pageSize = Math.min(200, Math.max(1, parseInt(url.searchParams.get('pageSize') || '20')))
    const totalPages = Math.ceil(totalResults / pageSize)
    const start = (page - 1) * pageSize
    const pagedBids = bids.slice(start, start + pageSize)

    // 7. 裁剪返回字段（列表不暴露 content）
    const sanitizedBids = pagedBids.map(b => ({
      id: b.id,
      title: b.title,
      source: b.source,
      industry: b.industry,
      region: b.region,
      method: b.method,
      budget: b.budget,
      date: b.date,
      deadline: b.deadline,
      buyer: b.buyer,
      code: b.code,
    }))

    // 8. 返回
    return new Response(JSON.stringify({
      bids: sanitizedBids,
      todayCount: data.todayCount || bids.length,
      updatedAt: data.updatedAt || null,
      totalResults,
      page,
      pageSize,
      totalPages,
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=120, s-maxage=300',
        'X-Robots-Tag': 'noindex',
      }
    })

  } catch (err) {
    return new Response(JSON.stringify({
      error: '服务器内部错误',
      code: 'INTERNAL_ERROR',
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}
