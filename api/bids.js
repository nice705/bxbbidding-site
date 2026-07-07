/**
 * GET /api/bids?page=1&pageSize=20&q=keyword
 * Returns paginated bids from the data
 */
import { loadBidsData } from './_data.js';

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);

  try {
    const data = await loadBidsData(request);
    let bids = data.bids || [];

    // Search filter
    const q = url.searchParams.get('q');
    if (q) {
      const keywords = q.toLowerCase().split(',').map(k => k.trim()).filter(Boolean);
      bids = bids.filter(b => {
        const text = (b.title + ' ' + (b.source || '') + ' ' + (b.region || '') + ' ' + (b.industry || '')).toLowerCase();
        return keywords.some(k => text.includes(k));
      });
    }

    // Region filter
    const region = url.searchParams.get('region');
    if (region && region !== '全国') {
      bids = bids.filter(b => b.region === region);
    }

    // Industry/category filter
    const industry = url.searchParams.get('industry');
    if (industry) {
      bids = bids.filter(b => b.industry === industry);
    }

    // Method filter
    const method = url.searchParams.get('method');
    if (method) {
      bids = bids.filter(b => b.method === method);
    }

    // Date filter
    const dateRange = url.searchParams.get('dateRange');
    if (dateRange && dateRange !== 'all') {
      const now = new Date();
      let cutoff;
      if (dateRange === 'today') {
        cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      } else if (dateRange === '3days') {
        cutoff = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);
      } else if (dateRange === 'week') {
        cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      } else if (dateRange === 'month') {
        cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      }
      if (cutoff) {
        const cutoffStr = cutoff.toISOString().slice(0, 10);
        bids = bids.filter(b => b.date >= cutoffStr);
      }
    }

    // Sort by date descending
    bids.sort((a, b) => (b.date || '').localeCompare(a.date || ''));

    // Pagination
    const page = Math.max(1, parseInt(url.searchParams.get('page') || '1'));
    const pageSize = Math.min(100, Math.max(1, parseInt(url.searchParams.get('pageSize') || '20')));
    const totalPages = Math.max(1, Math.ceil(bids.length / pageSize));
    const start = (page - 1) * pageSize;
    const paged = bids.slice(start, start + pageSize);

    return new Response(JSON.stringify({
      todayCount: data.todayCount || 0,
      updatedAt: data.updatedAt,
      items: paged,
      total: bids.length,
      page,
      pageSize,
      totalPages,
    }), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=120',
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
