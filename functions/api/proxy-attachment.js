/** WARNING: This file will be overwritten by deploy_production.py. Edit at functions/api/proxy-attachment.js */
/**
 * GET /api/proxy-attachment?url=https://...&local=...
 *       or POST with url and local in form body (to bypass WAF)
 *       or GET with b64_url parameter
 *
 * 代理下载附件文件，解决跨域限制。
 */
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  
  // Support both GET params and POST body
  let targetUrl, localFile;
  if (request.method === 'POST') {
    const formData = await request.formData();
    targetUrl = formData.get('url');
    localFile = formData.get('local');
  } else {
    // GET - try regular params, then base64
    targetUrl = url.searchParams.get('url');
    localFile = url.searchParams.get('local');
    // Also support base64-encoded URL (to bypass WAF for blocked domains)
    if (!targetUrl) {
      const b64Url = url.searchParams.get('b64_url');
      if (b64Url) {
        try {
          targetUrl = atob(b64Url);
        } catch (e) {
          return new Response('Invalid base64 url', { status: 400 });
        }
      }
    }
  }

  if (!targetUrl) {
    return new Response('Missing url parameter', { status: 400 });
  }

  if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
    return new Response('Invalid url protocol', { status: 400 });
  }

  // 1) 有本地文件 → CF Worker 从 VPS HTTP 抓取，通过 HTTPS 返回
  if (localFile) {
    const vpsUrl = 'http://121.40.176.240/attachments/' + encodeURIComponent(localFile);
    try {
      const resp = await fetch(vpsUrl, {
        headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': '*/*' },
        redirect: 'follow',
      });
      if (resp.ok) {
        const ext = localFile.split('.').pop().toLowerCase();
        const mimeMap = { 'pdf': 'application/pdf', 'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'zip': 'application/zip', 'rar': 'application/vnd.rar', 'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif' };
        const ct = mimeMap[ext] || 'application/octet-stream';
        const h = new Headers();
        h.set('Content-Type', ct);
        h.set('Content-Length', resp.headers.get('Content-Length') || '');
        h.set('Content-Disposition', `attachment; filename*=UTF-8''${encodeURIComponent(localFile)}`);
        h.set('Access-Control-Allow-Origin', '*');
        h.set('Cache-Control', 'public, max-age=3600');
        return new Response(resp.body, { status: 200, headers: h });
      }
    } catch (err) {
      // VPS 不可达 → 降级到 sessionRequired
    }
  }

  // 2) sessionRequired 源站 → 302/JS跳转
  const sessionRequired = ['jsggzy.jszwfw.gov.cn', 'ggzyfw.fujian.gov.cn', 'www.ccgp-hebei.gov.cn', 'ggzyjy.fzggw.nx.gov.cn', '222.75.70.90'];
  if (sessionRequired.some(d => targetUrl.includes(d))) {
    const escapedUrl = targetUrl.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const redirectHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${escapedUrl}"><script>window.location.href="${escapedUrl.replace(/&quot;/g, '\\x22')}";</script></head><body style="font-family:sans-serif;text-align:center;padding:40px"><p>正在跳转至源站下载...</p><a href="${escapedUrl}" style="color:#059669;font-size:16px">如果未跳转，点击此处下载</a></body></html>`;
    return new Response(redirectHtml, {
      status: 200,
      headers: {
        'Content-Type': 'text/html;charset=utf-8',
        'Access-Control-Allow-Origin': '*',
      }
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
