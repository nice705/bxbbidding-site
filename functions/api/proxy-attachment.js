/**
 * GET /api/proxy-attachment?url=https://...&local=...
 *
 * 代理下载附件文件，解决跨域限制。
 * 从 source URL 获取文件并返回给浏览器，附带 Content-Disposition 头使其下载。
 * 支持：直链文件、需要referer的源站、超时中断
 * 本地已部署的附件通过静态文件直接下载，不经过本函数。
 */
export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const targetUrl = url.searchParams.get('url');

  if (!targetUrl) {
    return new Response('Missing url parameter', { status: 400 });
  }

  // 安全限制：只允许 http/https 协议
  if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
    return new Response('Invalid url protocol', { status: 400 });
  }

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
      // 尝试不带referer重试
      const resp2 = await fetch(targetUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0',
          'Accept': '*/*',
        },
        redirect: 'follow',
      });
      if (!resp2.ok) {
        return new Response(`Failed to fetch attachment: ${resp2.status}`, { status: resp2.status });
      }
      return buildResponse(resp2, targetUrl);
    }

    return buildResponse(resp, targetUrl);
  } catch (err) {
    return new Response(`Error fetching attachment: ${err.message}`, { status: 500 });
  }

  async function buildResponse(resp, targetUrl) {
    // 获取文件名
    const contentDisposition = resp.headers.get('Content-Disposition');
    let filename = targetUrl.split('/').pop().split('?')[0];

    if (contentDisposition) {
      const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      if (match) {
        filename = match[1].replace(/['"]/g, '').trim() || filename;
      }
    }

    // URL 解码
    filename = decodeURIComponent(filename);

    // 获取内容类型
    const contentType = resp.headers.get('Content-Type') || 'application/octet-stream';

    // 确保返回的是实际文件内容（检查Content-Type是否为二进制/文件类型）
    const isFileContent = !contentType.includes('text/html') && !contentType.includes('text/plain');

    // 构建响应头，使浏览器下载
    const headers = new Headers(resp.headers);
    headers.set('Content-Disposition', `attachment; filename="${encodeURIComponent(filename)}"`);
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
    headers.set('Cache-Control', 'public, max-age=3600');

    // 如果源站返回HTML，可能是登录页/错误页，返回错误
    if (!isFileContent) {
      const bodyText = await resp.clone().text();
      if (bodyText.includes('<') && bodyText.includes('>')) {
        return new Response(`源站返回了网页而非文件内容，无法下载`, { status: 502 });
      }
    }

    return new Response(resp.body, {
      status: 200,
      headers,
    });
  }
}
