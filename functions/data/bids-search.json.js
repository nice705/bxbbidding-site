// 轻量搜索数据 - 无正文内容，仅用于列表搜索
// 从 bids-search.json.gz 解压数据
export async function onRequest(context) {
  const { request } = context;

  try {
    const url = new URL(request.url);
    const gzUrl = `${url.origin}/data/bids-search.json.gz`;

    const resp = await fetch(gzUrl);
    if (!resp.ok) {
      return new Response(
        JSON.stringify({ error: 'Search data not available', status: resp.status }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const arrayBuffer = await resp.arrayBuffer();
    const ds = new DecompressionStream('gzip');
    const writer = ds.writable.getWriter();
    writer.write(arrayBuffer);
    writer.close();
    const reader = ds.readable.getReader();
    const chunks = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const totalLen = chunks.reduce((a, c) => a + c.byteLength, 0);
    const result = new Uint8Array(totalLen);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.byteLength;
    }
    const jsonStr = new TextDecoder('utf-8').decode(result);

    return new Response(jsonStr, {
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=300',
        'Access-Control-Allow-Origin': '*',
      },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}