/** WARNING: This file will be overwritten by deploy_production.py. Edit at functions/api/proxy-attachment.js */
/**
 * GET /api/proxy-attachment?url=https://...&local=...
 *
 * 代理下载附件文件，解决跨域限制。
 * 策略（按优先级）：
 *   1) localFile → CF Worker 从 VPS HTTP 抓取，通过 HTTPS 返回（不 redirect 浏览器）
 *   2) sessionRequired 源站 → 302 直达（无本地文件时降级）
 *   3) 普通源站 → CF fetch 代理
 */
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const targetUrl = url.searchParams.get('url');
  const localFile = url.searchParams.get('local');

  if (!targetUrl) {
    return new Response('Missing url parameter', { status: 400 });
  }

  if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
    return new Response('Invalid url protocol', { status: 400 });
  }

  // 1) 有本地文件 → CF Worker 从 VPS HTTP 抓取，通过 HTTPS 返回
  //    浏览器永远不直接连接 VPS，解决混合内容和自签名证书问题
  if (localFile) {
    const vpsUrl = 'http://121.40.176.240/attachments/' + encodeURIComponent(localFile);
    try {
      const resp = await fetch(vpsUrl, {
        headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': '*/*' },
        redirect: 'follow',
      });
      if (resp.ok) {
        const cd = resp.headers.get('Content-Disposition') || `attachment; filename="${encodeURIComponent(localFile)}"`;
        const ct = resp.headers.get('Content-Type') || 'application/octet-stream';
        const h = new Headers(resp.headers);
        h.set('Content-Disposition', cd);
        h.set('Access-Control-Allow-Origin', '*');
        h.set('Cache-Control', 'public, max-age=3600');
        return new Response(resp.body, { status: 200, headers: h });
      }
    } catch (err) {
      // VPS 不可达 → 降级到 sessionRequired
    }
  }

  // 2) sessionRequired 源站 → 302 让浏览器直达（解决 CF IP 被 WAF 封禁）
  const sessionRequired = ['ggzyfw.fujian.gov.cn', 'www.ccgp-hebei.gov.cn', 'ggzyjy.fzggw.nx.gov.cn', '222.75.70.90', 'jsggzy.jszwfw.gov.cn'];
  if (sessionRequired.some(d => targetUrl.includes(d))) {
    return new Response(null, {
      status: 302,
      headers: { 'Location': targetUrl }
    });
  }

  // 3) ggzydl.cqggzy.com → 302 到远程中继
  if (targetUrl.includes('ggzydl.cqggzy.com')) {
    const relayUrl = 'http://121.40.176.240/proxy-attachment?url=' + encodeURIComponent(targetUrl);
    return new Response(null, {
      status: 302,
      headers: { 'Location': relayUrl }
    });
  }

  // 4) 普通源站 → CF fetch 代理
  try {
    const resp = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Referer': targetUrl,
      },
      redirect: 'follow',
    });

    if (!resp.ok) {
      const resp2 = await fetch(targetUrl, {
        headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': '*/*' },
        redirect: 'follow',
      });
      if (!resp2.ok) {
        return new Response('Failed to fetch attachment: ' + resp2.status, { status: resp2.status });
      }
      return buildResponse(resp2, targetUrl);
    }

    return buildResponse(resp, targetUrl);
  } catch (err) {
    return new Response('Error fetching attachment: ' + err.message, { status: 500 });
  }

  async function buildResponse(resp, targetUrl) {
    const cd = resp.headers.get('Content-Disposition');
    let filename = targetUrl.split('/').pop().split('?')[0];
    if (cd) {
      const m = cd.match(/filename[^;=\\n]*=((['\"]).*?\\2|[^;\\n]*)/);
      if (m) filename = m[1].replace(/['\"]/g, '').trim() || filename;
    }
    filename = decodeURIComponent(filename);
    const ct = resp.headers.get('Content-Type') || 'application/octet-stream';
    const isFile = !ct.includes('text/html') && !ct.includes('text/plain');
    const h = new Headers(resp.headers);
    h.set('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    h.set('Access-Control-Allow-Origin', '*');
    h.set('Cache-Control', 'public, max-age=3600');
    if (!isFile) {
      const body = await resp.clone().text();
      if (body.includes('<') && body.includes('>')) {
        return new Response('源站返回了网页而非文件内容，无法下载', { status: 502 });
      }
    }
    return new Response(resp.body, { status: 200, headers: h });
  }
}
