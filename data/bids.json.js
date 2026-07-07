/**
 * Serve bids.json from the gzipped static asset.
 * Cloudflare Pages has a 25 MiB per-file limit for static assets.
 * bids.json is ~32 MiB uncompressed → exceeds limit.
 * bids.json.gz is ~4.6 MiB → within limits.
 * This function decompresses on-the-fly and serves as JSON.
 */
export async function onRequest(context) {
  const { request, env } = context;

  try {
    // Fetch the gzipped static asset from the same deployment
    const url = new URL(request.url);
    const gzUrl = `${url.origin}/data/bids.json.gz`;
    const resp = await fetch(gzUrl);

    if (!resp.ok) {
      return new Response(
        JSON.stringify({ error: 'Data not available', status: resp.status }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Read the gzipped data as an ArrayBuffer
    const arrayBuffer = await resp.arrayBuffer();

    // Decompress using the built-in CompressionStream API
    const decompressed = await decompressGzip(arrayBuffer);

    return new Response(decompressed, {
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

/**
 * Decompress a gzip-compressed ArrayBuffer
 */
async function decompressGzip(buffer) {
  const ds = new DecompressionStream('gzip');
  const writer = ds.writable.getWriter();
  writer.write(buffer);
  writer.close();
  const reader = ds.readable.getReader();
  const chunks = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  // Combine chunks
  const totalLength = chunks.reduce((acc, chunk) => acc + chunk.byteLength, 0);
  const result = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  // Decode to string (assuming UTF-8)
  return new TextDecoder('utf-8').decode(result);
}
