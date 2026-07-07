/**
 * 共享数据加载工具
 *
 * 从 /data/bids.json 加载标讯数据。
 * 该请求由 functions/data/bids.json.js 截获，
 * 自动解压 data/bids.json.gz 后返回 JSON。
 * （gzip 压缩绕过 Cloudflare Pages 25MB 文件大小限制）
 */

/**
 * 加载全部标讯数据
 * @param {Request} request - 当前请求，用于构造同源 URL
 * @returns {Promise<{updatedAt: string, todayCount: number, bids: Array}>}
 */
export async function loadBidsData(request) {
  const url = new URL(request.url);
  const dataUrl = `${url.origin}/data/bids.json`;

  const resp = await fetch(dataUrl);
  if (!resp.ok) {
    throw new Error(`Failed to load bids data: ${resp.status}`);
  }

  return resp.json();
}

/**
 * 搜索标讯（标题 + 内容模糊匹配）
 * @param {Array} bids - 标讯数组
 * @param {string} query - 搜索关键词
 * @returns {Array} 匹配的标讯
 */
export function searchBids(bids, query) {
  if (!query || !query.trim()) return bids;

  const q = query.trim().toLowerCase();
  return bids.filter((bid) => {
    return (
      (bid.title && bid.title.toLowerCase().includes(q)) ||
      (bid.content && bid.content.toLowerCase().includes(q)) ||
      (bid.buyer && bid.buyer.toLowerCase().includes(q)) ||
      (bid.code && bid.code.toLowerCase().includes(q)) ||
      (bid.region && bid.region.toLowerCase().includes(q))
    );
  });
}

/**
 * 按行业筛选
 * @param {Array} bids
 * @param {string} industry
 * @returns {Array}
 */
export function filterByIndustry(bids, industry) {
  if (!industry || industry === '') return bids;
  return bids.filter((bid) => bid.industry === industry);
}

/**
 * 按来源筛选
 * @param {Array} bids
 * @param {string} source
 * @returns {Array}
 */
export function filterBySource(bids, source) {
  if (!source || source === '') return bids;
  return bids.filter((bid) => bid.source === source);
}

/**
 * 按地区筛选
 * @param {Array} bids
 * @param {string} region
 * @returns {Array}
 */
export function filterByRegion(bids, region) {
  if (!region || region === '' || region === '全国') return bids;
  return bids.filter((bid) => bid.region === region);
}

/**
 * 分页
 * @param {Array} items
 * @param {number} page - 页码（从 1 开始）
 * @param {number} pageSize - 每页条数
 * @returns {{ items: Array, total: number, page: number, pageSize: number, totalPages: number }}
 */
export function paginate(items, page = 1, pageSize = 20) {
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.max(1, Math.min(page, totalPages));
  const start = (safePage - 1) * pageSize;
  const pagedItems = items.slice(start, start + pageSize);

  return {
    items: pagedItems,
    total,
    page: safePage,
    pageSize,
    totalPages,
  };
}
