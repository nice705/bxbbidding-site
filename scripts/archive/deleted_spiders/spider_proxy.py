#!/usr/bin/env python3
"""
标讯宝 · Cloudflare Pages 代理 HTTP 模块

通过 Cloudflare Pages Worker 代理访问被阻断的中国境内网站。
代理 URL: https://bxbbidding-site-final-v3.pages.dev/proxy/?target=URL

所有爬虫统一通过此模块路由被阻断站点的请求。

用法:
    from scripts.spider_proxy import proxy_get, proxy_fetch
    resp = proxy_get("https://ecp.sgcc.com.cn/ecp2.0/portal/")
    print(resp.status_code, resp.text[:200])
"""

import json
import time
import urllib.parse
from typing import Optional, Any
from datetime import datetime

import requests

# ── 常量 ──────────────────────────────────────────────────────────────
PROXY_BASE = "https://bxbbidding-site-final-v3.pages.dev/proxy/"

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ── 已知被阻断的域名列表 ─────────────────────────────────────────────
BLOCKED_DOMAINS = [
    "plap.cn",
    "www.plap.cn",
    "ecp.sgcc.com.cn",
    "newbidding.sgcc.com.cn",
    "b2b.10086.cn",
    "www.chinaunicombidding.cn",
    "caigou.chinatelecom.com.cn",
    "www.cnpcbidding.com",
    "bidding.sinopec.com",
    "buy.cnooc.com.cn",
    "chinabidding.com",
    "www.chinabidding.com",
    "ggzy.zj.gov.cn",
    "ggzy.gd.gov.cn",
    "ggzy.shandong.gov.cn",
    "ggzy.sichuan.gov.cn",
    "ggzy.jszwfw.gov.cn",
    "ggzy.hubei.gov.cn",
    "ggzy.henan.gov.cn",
    "ggzy.hebei.gov.cn",
    "ggzy.fujian.gov.cn",
    "ggzy.hunan.gov.cn",
    "ggzy.anhui.gov.cn",
    "ggzy.jiangxi.gov.cn",
    "ggzy.shanxi.gov.cn",
    "ggzy.liaoning.gov.cn",
    "ggzy.jilin.gov.cn",
    "ggzy.hlj.gov.cn",
    "ggzy.shaanxi.gov.cn",
    "ggzy.gansu.gov.cn",
    "ggzy.qinghai.gov.cn",
    "ggzy.yunnan.gov.cn",
    "ggzy.guizhou.gov.cn",
    "ggzy.hainan.gov.cn",
    "ggzy.nmg.gov.cn",
    "ggzy.xinjiang.gov.cn",
    "ggzy.xizang.gov.cn",
    "ggzy.guangxi.gov.cn",
    "ggzy.ningxia.gov.cn",
    "ggzy.cq.gov.cn",
    "ggzy.tj.gov.cn",
    "ggzy.beijing.gov.cn",
    "ggzy.sh.gov.cn",
]

# ── ProxyResponse ─────────────────────────────────────────────────────


class ProxyResponse:
    """
    模拟 requests.Response 的轻量包装。

    属性:
        text: HTML 文本
        content: bytes 原始内容
        status_code: HTTP 状态码
        ok: 是否成功 (status_code == 200)
        url: 最终请求 URL
        elapsed: 耗时秒数
    """

    def __init__(self, text: str = "", status_code: int = 200, url: str = ""):
        self._text = text
        self._content = text.encode("utf-8")
        self.status_code = status_code
        self.url = url
        self.elapsed = 0.0
        self.reason = ""

    @property
    def text(self) -> str:
        return self._text

    @property
    def content(self) -> bytes:
        return self._content

    @property
    def ok(self) -> bool:
        return self.status_code == 200

    def __repr__(self):
        return f"<ProxyResponse [{self.status_code}] {len(self._text)} chars>"


# ── 核心请求函数 ─────────────────────────────────────────────────────


def build_proxy_url(target_url: str) -> str:
    """构建 Cloudflare Pages 代理 URL"""
    encoded = urllib.parse.quote(target_url, safe="")
    return f"{PROXY_BASE}?target={encoded}"


def is_blocked_domain(url: str) -> bool:
    """
    检查 URL 是否属于已知被阻断的域名。

    参数:
        url: 完整 URL 或域名

    返回:
        True 如果域名在阻断列表中
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc or url  # 如果无法解析，直接匹配

    # 去除端口
    if ":" in domain:
        domain = domain.split(":")[0]

    # 精确匹配
    if domain in BLOCKED_DOMAINS:
        return True

    # 通配匹配: ggzy.*
    for blocked in BLOCKED_DOMAINS:
        if blocked.startswith("*."):
            suffix = blocked[1:]  # .ggzy.* 模式
            if domain.endswith(suffix):
                return True

    # 特殊匹配: ggzy.*.gov.cn
    if domain.startswith("ggzy.") or ".ggzy." in domain:
        return True

    return False


def proxy_get(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Optional[ProxyResponse]:
    """
    通过 Cloudflare Pages 代理发送 GET 请求。

    参数:
        url: 目标 URL
        timeout: 超时秒数
        retries: 重试次数

    返回:
        ProxyResponse 对象，失败返回 None
    """
    return proxy_fetch(url, method="GET", timeout=timeout, retries=retries)


def proxy_post(
    url: str,
    data: Any = None,
    json_data: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Optional[ProxyResponse]:
    """
    通过 Cloudflare Pages 代理发送 POST 请求。

    参数:
        url: 目标 URL
        data: 表单数据
        json_data: JSON 数据
        timeout: 超时秒数
        retries: 重试次数

    返回:
        ProxyResponse 对象，失败返回 None
    """
    body = {}
    if data is not None:
        body["data"] = data
    if json_data is not None:
        body["json"] = json_data

    return proxy_fetch(
        url, method="POST", body=body, timeout=timeout, retries=retries
    )


def proxy_fetch(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Optional[ProxyResponse]:
    """
    通用代理请求函数。

    向 CF Pages 代理发送请求，代理负责转发到目标 URL。

    参数:
        url: 目标 URL
        method: HTTP 方法 (GET/POST)
        headers: 自定义请求头
        body: POST 请求体 (dict)
        timeout: 超时秒数
        retries: 重试次数

    返回:
        ProxyResponse 对象，失败返回 None
    """
    proxy_url = build_proxy_url(url)
    req_headers = DEFAULT_HEADERS.copy()
    if headers:
        req_headers.update(headers)

    if body:
        req_headers["Content-Type"] = "application/json"

    for attempt in range(1, retries + 1):
        start = time.time()
        try:
            if method.upper() == "GET":
                resp = requests.get(
                    proxy_url,
                    headers=req_headers,
                    timeout=timeout,
                )
            else:
                payload = body or {}
                resp = requests.post(
                    proxy_url,
                    headers=req_headers,
                    json=payload,
                    timeout=timeout,
                )

            elapsed = time.time() - start
            result = ProxyResponse(
                text=resp.text,
                status_code=resp.status_code,
                url=url,
            )
            result.elapsed = elapsed
            result.reason = resp.reason if hasattr(resp, "reason") else ""

            # 检查代理自身是否返回错误
            if resp.status_code == 502:
                print(f"  ⚠ CF 代理 502: {url[:80]} (try {attempt})")
            elif resp.status_code == 200:
                # 额外检查: 代理返回的内容是否是"请求失败"
                if len(resp.text) < 50:
                    # 可能是空响应
                    pass
                return result
            else:
                print(f"  ⚠ CF 代理 HTTP {resp.status_code}: {url[:80]} (try {attempt})")

        except requests.Timeout:
            print(f"  ⚠ CF 代理超时: {url[:80]} (try {attempt})")
        except requests.ConnectionError as e:
            print(f"  ⚠ CF 代理连接失败: {e} (try {attempt})")
        except Exception as e:
            print(f"  ⚠ CF 代理请求异常: {e} (try {attempt})")

        if attempt < retries:
            time.sleep(2 ** attempt)

    return None


def proxy_fetch_html(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """
    快捷函数: 通过代理获取 HTML 文本。

    参数:
        url: 目标 URL
        timeout: 超时秒数

    返回:
        HTML 字符串，失败返回 None
    """
    resp = proxy_get(url, timeout=timeout)
    if resp and resp.ok:
        return resp.text
    return None


def check_proxy_connectivity() -> bool:
    """
    测试 CF Pages 代理连通性。

    访问一个已知可用的网站来验证代理是否工作。

    返回:
        True 如果代理可用
    """
    test_url = "http://httpbin.org/get"
    resp = proxy_get(test_url, timeout=15)
    ok = resp is not None and resp.ok
    if ok:
        print(f"  ✅ CF 代理连通性检查通过")
    else:
        print(f"  ⚠ CF 代理连通性检查失败")
    return ok


# ── 批量域名检查 ─────────────────────────────────────────────────────


def check_domains(domains: list[str] = None) -> dict:
    """
    批量测试域名是否可通过代理访问。

    参数:
        domains: 域名列表，默认使用 BLOCKED_DOMAINS

    返回:
        {domain: {"accessible": bool, "status": int, "length": int}}
    """
    if domains is None:
        domains = BLOCKED_DOMAINS

    results = {}
    for domain in domains:
        url = f"https://{domain}"
        print(f"  🔍 测试 {domain}...", end=" ", flush=True)
        resp = proxy_get(url, timeout=20)
        if resp and resp.ok:
            print(f"✅ HTTP {resp.status_code} ({len(resp.text)} chars)")
            results[domain] = {
                "accessible": True,
                "status": resp.status_code,
                "length": len(resp.text),
            }
        else:
            status = resp.status_code if resp else "N/A"
            print(f"❌ HTTP {status}")
            results[domain] = {
                "accessible": False,
                "status": status if resp else 0,
                "length": 0,
            }
    return results


# ── 自测 ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 60)
    print("  CF Pages 代理模块自测")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 测试连通性
    print("\n📡 连通性测试:")
    check_proxy_connectivity()

    # 测试被阻断域名
    print("\n📡 被阻断站点测试:")
    test_domains = [
        "ecp.sgcc.com.cn",
        "ggzy.zj.gov.cn",
        "b2b.10086.cn",
        "bidding.sinopec.com",
    ]
    results = check_domains(test_domains)

    # 汇总
    accessible = sum(1 for r in results.values() if r["accessible"])
    print(f"\n{'='*60}")
    print(f"  可访问: {accessible}/{len(results)}")
    print(f"{'='*60}")
