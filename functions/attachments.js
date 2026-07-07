/** HTTPS proxy for /attachments/{filename} */
export async function onRequest(context) {
  const url = new URL(context.request.url);
  const filename = url.pathname.replace('/attachments/', '');
  if (!filename || filename.includes('..')) {
    return new Response('Invalid', { status: 400 });
  }
  try {
    const resp = await fetch('http://121.40.176.240/attachments/' + encodeURIComponent(filename), {
      headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': '*/*' }
    });
    if (!resp.ok) return new Response('Not found', { status: 404 });
    const headers = new Headers({
      'Content-Type': resp.headers.get('Content-Type') || 'application/octet-stream',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=86400'
    });
    return new Response(resp.body, { status: 200, headers });
  } catch (e) {
    return new Response('Error: ' + e.message, { status: 500 });
  }
}
