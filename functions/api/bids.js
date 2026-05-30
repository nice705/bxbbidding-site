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

    // Pagination
    const page = Math.max(1, parseInt(url.searchParams.get('page') || '1'));
    const pageSize = Math.min(100, Math.max(1, parseInt(url.searchParams.get('pageSize') || '20')));
    const start = (page - 1) * pageSize;
    const paged = bids.slice(start, start + pageSize);

    return new Response(JSON.stringify({
      total: bids.length,
      page,
      pageSize,
      updatedAt: data.updatedAt,
      bids: paged
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
