/**
 * GET /attachments/{filename}
 *
 * HTTPS 代理：将 HTTP 源站的附件通过 CF Pages HTTPS 提供服务，
 * 解决混合内容（Mixed Content）警告。
 *
 * 源站: http://121.40.176.240/attachments/{filename}
 * 客户端: https://qgbxb.com/attachments/{filename}
 */

const SOURCE_BASE = 'http://121.40.176.240';

export async function onRequest(context) {
  const { request, params } = context;
  const filename = params.filename;

  if (!filename) {
    return new Response('Missing filename', { status: 400 });
  }

  // 安全：禁止路径遍历
  if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
    return new Response('Invalid filename', { status: 400 });
  }

  const targetUrl = `${SOURCE_BASE}/attachments/${encodeURIComponent(filename)}`;

  try {
    const resp = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
      },
      redirect: 'follow',
    });

    if (!resp.ok) {
      return new Response(`Failed to fetch attachment: ${resp.status}`, { status: resp.status });
    }

    // 透传 Content-Type，保留原文件类型
    const contentType = resp.headers.get('Content-Type') || 'application/octet-stream';

    // 透传 Content-Disposition（若有），否则使用下载附件头
    let contentDisposition = resp.headers.get('Content-Disposition');
    if (!contentDisposition) {
      contentDisposition = `attachment; filename="${encodeURIComponent(filename)}"`;
    }

    // 构建响应头
    const headers = new Headers({
      'Content-Type': contentType,
      'Content-Disposition': contentDisposition,
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Cache-Control': 'public, max-age=86400',
    });

    return new Response(resp.body, {
      status: 200,
      headers,
    });
  } catch (err) {
    return new Response(`Error fetching attachment: ${err.message}`, { status: 500 });
  }
}
