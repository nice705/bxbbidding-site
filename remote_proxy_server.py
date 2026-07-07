#!/usr/bin/env python3
"""
远程附件下载代理服务器
运行在远程服务器 121.40.176.240
用于代理 ggzydl.cqggzy.com 的附件下载（CF Worker IP 被 WAF 封禁）

启动: python3 remote_proxy_server.py
端口: 8765
"""

import http.server
import urllib.request
import urllib.parse
import os
import sys

PORT = 8765

# 需要带 Referer 的源站
REFERER_MAP = {
    'ggzydl.cqggzy.com': 'https://www.cqggzy.com/',
}

class AttachmentProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if parsed.path == '/proxy-attachment':
            target_url = params.get('url', [None])[0]
            if not target_url:
                self.send_error(400, 'Missing url parameter')
                return
            
            # 安全检查：只允许 http/https
            if not target_url.startswith('http://') and not target_url.startswith('https://'):
                self.send_error(400, 'Invalid protocol')
                return
            
            self.proxy_fetch(target_url)
        elif parsed.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_error(404, 'Not found')
    
    def proxy_fetch(self, target_url):
        # 确定 Referer
        referer = None
        for domain, ref in REFERER_MAP.items():
            if domain in target_url:
                referer = ref
                break
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
        }
        if referer:
            headers['Referer'] = referer
        
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
                content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                
                # 获取文件名
                filename = target_url.split('/')[-1].split('?')[0]
                cd = resp.headers.get('Content-Disposition', '')
                if cd:
                    import re
                    m = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', cd)
                    if m:
                        filename = m.group(1).strip('\'"')
                
                # URL 解码后作为显示名，但Content-Disposition用URL编码版本避免latin-1错误
                filename_raw = urllib.parse.unquote(filename)
                if not filename_raw or filename_raw == '':
                    filename_raw = 'download'
                
                # ASCII安全的文件名（URL编码，用于HTTP头）
                filename_safe = urllib.parse.quote(filename_raw, safe='')
                
                if 'text/html' in content_type:
                    text = content[:500].decode('utf-8', errors='replace')
                    if '<' in text and '>' in text:
                        self._send_text_error(502, f'源站返回了网页而非文件: {text[:200]}')
                        return
                
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Disposition', f'attachment; filename="{filename_safe}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                
        except urllib.error.HTTPError as e:
            msg = f'HTTP Error: {e.code} {e.reason}'
            self._send_text_error(e.code, msg)
        except urllib.error.URLError as e:
            self._send_text_error(502, f'URL Error: {e.reason}')
        except Exception as e:
            self._send_text_error(500, f'Proxy Error: {str(e)}')

    def _send_text_error(self, code, message):
        """发送文本错误响应，避免 latin-1 编码问题"""
        body = message.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def log_message(self, format, *args):
        """Suppress default logging to stderr"""
        pass

if __name__ == '__main__':
    print(f'Starting attachment proxy on port {PORT}...')
    server = http.server.HTTPServer(('0.0.0.0', PORT), AttachmentProxyHandler)
    print(f'Serving at http://0.0.0.0:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.server_close()
