/**
 * GET /api/bids/:id
 * Returns a single bid by ID
 */
import { loadBidsData } from '../_data.js';

export async function onRequest(context) {
  const { params, request } = context;
  const id = params.id;

  try {
    const data = await loadBidsData(request);
    const bid = (data.bids || []).find(b => b.id === id);

    if (!bid) {
      return new Response(JSON.stringify({ error: 'Bid not found', id }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
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
