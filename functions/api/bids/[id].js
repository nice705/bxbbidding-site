/**
 * GET /api/bids/:id
 * Returns a single bid by ID — never returns 404
 */
import { loadBidsData } from '../_data.js';

export async function onRequest(context) {
  const { params, request } = context;
  const id = params.id;

  try {
    const data = await loadBidsData(request);
    let bid = (data.bids || []).find(b => b.id === id);

    if (!bid) {
      // Return a placeholder bid instead of 404
      bid = {
        id: id,
        title: '标讯详情',
        source: '',
        sourceUrl: '',
        content: '',
        date: '',
        region: '',
        industry: '',
        method: '',
        buyer: '',
        deadline: '',
        code: '',
        budget: ''
      };
    }

    return new Response(JSON.stringify({
      updatedAt: data.updatedAt,
      bid
    }), {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=300',
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
