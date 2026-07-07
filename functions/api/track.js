// 标讯宝 · 访客跟踪代理 (CF Pages Function)
// 接收 HTTPS 请求，转发到后端跟踪服务器
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  
  const page = url.searchParams.get('p') || '';
  const ref = url.searchParams.get('r') || '';
  const dur = url.searchParams.get('d') || '0';
  
  // 转发到后端跟踪服务器
  const trackUrl = `http://121.40.176.240/track?p=${encodeURIComponent(page)}&r=${encodeURIComponent(ref)}&d=${dur}&_=${Date.now()}`;
  
  try {
    await fetch(trackUrl, {
      method: 'GET',
      headers: { 'User-Agent': request.headers.get('User-Agent') || '' },
      signal: AbortSignal.timeout(5000)
    });
  } catch(e) {
    // 后端不可达不影响用户，静默失败
  }
  
  // 返回 1x1 透明 GIF
  return new Response(
    new Uint8Array([71,73,70,56,57,97,1,0,1,0,128,0,0,255,255,255,0,0,0,33,249,4,0,0,0,0,0,44,0,0,0,0,1,0,1,0,0,2,2,68,1,0,59]),
    {
      headers: {
        'Content-Type': 'image/gif',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Access-Control-Allow-Origin': '*'
      }
    }
  );
}
