// Quick test: CF Worker fetching from jsggzy directly
// This runs on Cloudflare's edge network
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const dl = url.searchParams.get('dl');
  
  if (!dl) {
    // Test direct fetch from jsggzy
    const jsggzyUrl = 'https://jsggzy.jszwfw.gov.cn/EpointWebBuilder_jsggzy/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=2c9eb1ce9f29eb8e019f36ac399d62b1&appUrlFlag=JSWZTP&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a';
    
    try {
      const resp = await fetch(jsggzyUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Accept': '*/*',
          'Referer': 'https://jsggzy.jszwfw.gov.cn/jyxx/003001/003001001/20260706/2c9eb1ce9f29eb8e019f366150ab52c1.html',
        },
        redirect: 'follow',
      });
      
      const text = await resp.text();
      const headers = {};
      resp.headers.forEach((v, k) => { headers[k] = v; });
      
      return new Response(JSON.stringify({
        status: resp.status,
        statusText: resp.statusText,
        headers: headers,
        bodyLength: text.length,
        bodyStart: text.substring(0, 200),
      }, null, 2), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
  
  return new Response('ok');
}
