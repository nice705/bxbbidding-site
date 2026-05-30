#!/usr/bin/env python3
"""
标讯宝 · CEBPub Playwright 深度爬虫

原理：
  1. 列表页用 requests 抓（已有的 crawl_list_page 逻辑）
  2. 详情页用 Playwright 打开 ctbpsp.com SPA
  3. 拦截 XHR API → DES 解密 → 获取 metadata + PDF URL
  4. 通过浏览器上下文下载 PDF → 提取全文

绕过通道：
  ✅ WAF JS Challenge → Playwright 真实浏览器自动通过
  ✅ PDF 直连被封 → 通过浏览器 fetch 下载（credentials: include）
  ✅ API 加密 → 硬编码 DES key 解密

运行：
  python3 scripts/spider_cebpub_playwright.py [--category 90] [--start 2026-05-20] [--end 2026-05-22]
"""

import asyncio
import base64
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlencode

# Use full Chromium browser (not headless-shell) to avoid libnspr4 dependency
os.environ["PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL"] = "false"

import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import DES

from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# ── 配置 ──
LIST_URL = "https://bulletin.cebpubservice.com/xxfbcmses/search/bulletin.html"
API_TPL = "https://ctbpsp.com/cutominfoapi/bulletin/{uuid}/uid/0/token/0"
PDF_VIEWER_TPL = "https://ctbpsp.com/web_pdf/pdfjs-dist/web/viewer.html?file={pdf_url}"
DETAIL_URL_TPL = "https://ctbpsp.com/#/bulletinDetail?uuid={uuid}"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

# DES 加密密钥（从 JS 中提取）
DES_KEY = b"1qaz@wsx"

CATEGORIES = {
    "88": "全部", "89": "更正公告", "90": "中标结果",
    "91": "中标候选人", "92": "资格预审",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bulletin.cebpubservice.com/",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MIN_DELAY = 1.0
MAX_DELAY = 3.0
PAGE_SIZE = 15


# ── DES 解密（与前端一致） ──
def des_decrypt(encrypted_b64: str) -> dict | None:
    """解密 ctbpsp.com 的 DES 加密 API 响应"""
    try:
        # 补全 base64 padding
        missing = len(encrypted_b64) % 4
        if missing:
            encrypted_b64 += "=" * (4 - missing)
        decoded = base64.b64decode(encrypted_b64)
        cipher = DES.new(DES_KEY, DES.MODE_ECB)
        decrypted = cipher.decrypt(decoded)
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 8:
            unpadded = decrypted[:-pad_len]
        else:
            unpadded = decrypted
        return json.loads(unpadded.decode("utf-8"))
    except Exception as e:
        print(f"    ⚠ DES 解密失败: {e}")
        return None


# ── 元数据提取（与主 spider 一致） ──
INDUSTRY_KEYWORDS = {
    "医疗": ["医院", "医疗", "药品", "医用", "CT", "核磁", "超声", "救护", "手术", "卫生", "临床", "医药", "医疗器械", "同仁医院", "人民医院", "疾控"],
    "IT信息化": ["信息化", "软件", "系统", "平台", "网络", "服务器", "交换机", "计算机", "机房", "数据", "IT", "互联网", "数字化", "智能", "AI", "物联网", "电信", "代码开发", "信息系统"],
    "工程建设": ["工程", "施工", "建设", "装修", "修缮", "道路", "桥梁", "市政", "建筑", "改造", "维修", "加固", "通风工程", "消防改造"],
    "教育科研": ["学校", "学院", "大学", "教育", "教学", "教室", "图书", "科研", "培训", "教材"],
    "环保环卫": ["环保", "环卫", "垃圾", "污水", "环境", "绿化", "清洁", "保洁", "环卫车辆", "节能"],
    "安防消防": ["安防", "监控", "门禁", "消防", "安保", "安全", "报警"],
    "物业后勤": ["物业", "食堂", "餐饮", "保安", "后勤", "劳务", "服务", "外包", "租赁服务"],
    "交通运输": ["交通", "车辆", "公交", "出租车", "运输", "物流", "航运", "铁路", "公路", "塔式起重机", "推土机"],
    "房屋建筑": ["房屋建筑", "住宅", "房地产", "建筑", "施工"],
    "农林牧渔": ["农业", "林业", "畜牧", "渔业", "种子", "化肥", "农药", "农田", "水利"],
    "文体旅游": ["体育", "文化", "会展", "展览", "演出", "旅游", "酒店"],
    "机械设备": ["设备", "机械", "机电", "电气", "仪器", "仪表", "制造", "变压器", "配电柜", "柴油发电机组"],
    "能源电力": ["电力", "能源", "光伏", "风电", "太阳能", "电网", "供电", "配电", "发电", "铝业", "百河铝业"],
}

PROVINCE_KEYWORDS = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "台湾", "广西", "内蒙古", "西藏", "宁夏", "新疆",
]


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def is_good_content(content: str) -> bool:
    if not content or len(content) <= 100:
        return False
    blocked = ["页面访问提示", "暂停访问", "PDF 文件"]
    return not any(kw in content for kw in blocked)


def load_existing_ids() -> set:
    if not os.path.exists(DATA_FILE):
        return set()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {md5(b["sourceUrl"]) for b in data.get("bids", [])}
    except (json.JSONDecodeError, KeyError):
        return set()


def load_existing_bids() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("bids", [])
    except (json.JSONDecodeError, KeyError):
        return []


def save_bids(bids: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for b in bids if b.get("date") == today_str)
    output = {
        "todayCount": today_count,
        "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "bids": bids,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 写入 {len(bids)} 条标讯 → {DATA_FILE}")


def extract_industry(title: str, industry_from_list: str = "") -> str:
    if industry_from_list and industry_from_list not in ("其他", "", "不限"):
        if industry_from_list in INDUSTRY_KEYWORDS:
            return industry_from_list
        for ind in INDUSTRY_KEYWORDS:
            if ind in industry_from_list or industry_from_list in ind:
                return ind
        return industry_from_list
    full_text = title
    for ind, kws in INDUSTRY_KEYWORDS.items():
        if any(kw in full_text for kw in kws):
            return ind
    return ""


def extract_region(region_from_list: str = "", title: str = "") -> str:
    if region_from_list and region_from_list not in ("", "全国"):
        region = region_from_list.strip("【】").strip()
        if region in PROVINCE_KEYWORDS:
            return region
    for prov in PROVINCE_KEYWORDS:
        if prov in title:
            return prov
    return ""


def extract_method(title: str) -> str:
    method_patterns = [
        (r"公开招标", "公开招标"), (r"竞争性磋商", "竞争性磋商"),
        (r"竞争性谈判", "竞争性谈判"), (r"单一来源", "单一来源"),
        (r"询价|询比采购|询比公告", "询价"),
        (r"中标结果|中标公告", "中标公告"), (r"中标候选人", "中标候选人"),
        (r"更正公告|变更公告", "更正公告"), (r"资格预审", "资格预审"),
        (r"邀请招标", "邀请招标"), (r"谈判采购", "谈判采购"),
        (r"竞价公告|竞价", "竞价"), (r"比选", "比选"),
        (r"方案征集|征集公告", "方案征集"), (r"直接采购", "直接采购"),
        (r"招标公告", "公开招标"),
    ]
    for pat, name in method_patterns:
        if re.search(pat, title):
            return name
    return ""


def extract_deadline(td_element) -> str:
    if not td_element:
        return ""
    text = td_element.get_text(strip=True)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    td_id = td_element.get("id", "")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", td_id)
    if m:
        return m.group(1)
    return ""


def extract_budget_from_text(text: str) -> str:
    patterns = [
        r"预算金额[：:]?\s*([0-9,，.]+)\s*万元",
        r"预算金额[：:]?\s*([0-9,，.]+)\s*元",
        r"预算[：:]?\s*([0-9,，.]+)\s*万元",
        r"预算[：:]?\s*([0-9,，.]+)\s*元",
        r"项目预算[：:]?\s*([0-9,，.]+)\s*万元",
        r"项目预算[：:]?\s*([0-9,，.]+)\s*元",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).replace(",", "").replace("，", "")
    return ""


def extract_code_from_text(text: str) -> str:
    patterns = [
        r"项目编号[：:]?\s*([A-Za-z0-9\-_（）()]+)",
        r"招标编号[：:]?\s*([A-Za-z0-9\-_（）()]+)",
        r"采购编号[：:]?\s*([A-Za-z0-9\-_（）()]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()[:50]
    return ""


# ── 列表页爬取（复用已有逻辑） ──
def safe_request(url: str, session: requests.Session, headers: dict = None, **kwargs) -> requests.Response | None:
    if headers is None:
        headers = HEADERS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (404, 403):
                return None
            else:
                print(f"  ⚠ HTTP {resp.status_code} {url[:80]} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {e} (attempt {attempt})")
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    return None


def crawl_list_page(session: requests.Session, params: dict) -> list[dict]:
    items = []
    url = LIST_URL + "?" + urlencode(params)
    resp = safe_request(url, session)
    if resp is None:
        return items
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table_text")
    if not table:
        return items
    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        title_cell = cells[0]
        link = title_cell.find("a")
        if not link:
            continue
        href = link.get("href", "")
        uuid_match = re.search(r"urlOpen\('([a-f0-9\-]+)'\)", href)
        if not uuid_match:
            continue
        uuid_str = uuid_match.group(1)
        title = link.get("title") or link.get_text(strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        source_url = DETAIL_URL_TPL.format(uuid=uuid_str)
        bid_id = md5(source_url)
        items.append({
            "id": bid_id[:12],
            "uuid": uuid_str,
            "title": title,
            "industry_list": cells[1].get_text(strip=True),
            "region_list": cells[2].get_text(strip=True),
            "source_channel": cells[3].get_text(strip=True),
            "date": cells[4].get_text(strip=True),
            "deadline_td": cells[5],
            "sourceUrl": source_url,
        })
    return items


# ── Playwright 深度详情爬取 ──
class CEBPubPlaywrightSpider:
    """使用 Playwright 绕过 WAF，获取公告全文 + 元数据"""

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.browser = None
        self.context = None

    async def _init_browser(self):
        """初始化 Playwright 浏览器"""
        p = await async_playwright().start()
        self._playwright = p
        # 显式指定完整 Chromium 路径，并传递 LD_LIBRARY_PATH
        chromium_path = os.path.expanduser(
            "~/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome"
        )
        launch_env = os.environ.copy()
        # libnspr4.so 位于 LD_LIBRARY_PATH 中，但 Playwright 子进程不继承它
        launch_env["LD_LIBRARY_PATH"] = (
            "/tmp/libfix/root/usr/lib/x86_64-linux-gnu:"
            "/tmp/libfix/root/lib/x86_64-linux-gnu:"
            + launch_env.get("LD_LIBRARY_PATH", "")
        )
        self.browser = await p.chromium.launch(
            headless=True,
            executable_path=chromium_path,
            env=launch_env,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        # 使用完整 Chromium（headless-shell 缺 libnspr4）
        self.context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN"
        )

    async def _get_page(self):
        """获取一个隔离的 page 实例，应用 Stealth"""
        page = await self.context.new_page()
        st = Stealth()
        await st.apply_stealth_async(page)
        return page

    async def fetch_detail(self, uuid: str, session: requests.Session = None) -> dict | None:
        """
        通过 Playwright 获取公告详情 + PDF
        
        返回:
          {
            "api_data": {...},       # 解密后的 API 元数据
            "pdf_text": "...",       # PDF 提取的全文
            "pdf_url": "...",        # PDF 下载地址
          }
          或 None（失败）
        """
        if self.browser is None:
            await self._init_browser()

        page = await self._get_page()
        try:
            # 开门页，通过 WAF 挑战（加载主站获取有效 cookies）
            await page.goto("https://ctbpsp.com/", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # 通过浏览器内 fetch 直接调用 API（携带 cookies 通过 WAF）
            api_url = API_TPL.format(uuid=uuid)
            api_result = await page.evaluate(f"""async () => {{
                try {{
                    const resp = await fetch("{api_url}", {{
                        credentials: "include",
                        headers: {{ "Accept": "application/json, text/plain, */*" }}
                    }});
                    const text = await resp.text();
                    return {{ status: resp.status, data: text }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}""")

            if api_result.get("error"):
                print(f"    ⚠ API 调用失败: {api_result['error']}")
                return None

            if api_result.get("status") != 200:
                print(f"    ⚠ API HTTP {api_result['status']}")
                return None

            api_raw = api_result["data"]
            if not api_raw.startswith('"'):
                print(f"    ⚠ API 响应不是加密格式")
                return None

            # 解密 API 数据
            api_data = des_decrypt(api_raw[0])
            if not api_data or not api_data.get("success"):
                print(f"    ⚠ API 解密失败")
                return None

            data = api_data.get("data", {})
            pdf_url = data.get("pdfUrl", "")

            # 下载 PDF（通过浏览器上下文，携带 cookies）
            pdf_text = ""
            if pdf_url:
                pdf_text = await self._download_pdf(page, pdf_url)

            return {
                "api_data": api_data,
                "pdf_text": pdf_text,
                "pdf_url": pdf_url,
            }

        except Exception as e:
            print(f"    ⚠ Playwright 详情抓取失败: {e}")
            traceback.print_exc()
            return None
        finally:
            await page.close()

    async def _download_pdf(self, page, pdf_url: str) -> str:
        """通过浏览器上下文下载 PDF 并提取文本"""
        try:
            # 使用浏览器内 fetch（携带 cookies 通过 WAF）
            pdf_info = await page.evaluate(f"""async () => {{
                try {{
                    const resp = await fetch("{pdf_url}", {{
                        credentials: "include"
                    }});
                    const blob = await resp.blob();
                    const buffer = await blob.arrayBuffer();
                    const bytes = new Uint8Array(buffer);
                    // 检查前 4 字节是否是 %PDF
                    const header = String.fromCharCode(bytes[0], bytes[1], bytes[2]);
                    if (header !== '%PD') return {{error: 'not_pdf', status: resp.status}};
                    return {{
                        status: resp.status,
                        type: blob.type,
                        size: blob.size,
                        base64: btoa(String.fromCharCode(...bytes))
                    }};
                }} catch(e) {{
                    return {{error: e.message}};
                }}
            }}""")

            if pdf_info.get("error"):
                print(f"    ⚠ PDF 下载失败: {pdf_info['error']}")
                return ""

            if pdf_info.get("status") != 200:
                print(f"    ⚠ PDF HTTP {pdf_info['status']}")
                return ""

            b64_data = pdf_info.get("base64", "")
            if not b64_data:
                return ""

            pdf_bytes = base64.b64decode(b64_data)
            print(f"    ✓ PDF 下载成功: {len(pdf_bytes)} bytes")

            # 提取文本
            if fitz is None:
                return ""

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            texts = []
            for p in doc:
                t = p.get_text()
                if t and t.strip():
                    texts.append(t.strip())
            doc.close()
            full_text = "\n\n".join(texts)
            print(f"    ✓ PDF 提取 {len(full_text)} 字")
            return full_text

        except Exception as e:
            print(f"    ⚠ PDF 处理失败: {e}")
            return ""

    async def close(self):
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()


# ── 主流程 ──
def build_bid_from_api(
    uuid: str,
    api_data: dict,
    pdf_text: str,
    title_from_list: str,
    industry_list: str,
    region_list: str,
    category_id: str,
) -> dict:
    """将 API 响应 + PDF 文本合成为标讯条目"""
    data = api_data.get("data", {})

    # 使用列表页标题或 API 标题
    title = title_from_list or data.get("bulletinName", "")

    # 元数据（优先用 API 数据，更准确）
    industry = extract_industry(title, industry_list)
    region = extract_region(region_list, title)
    method = extract_method(title)
    budget = extract_budget_from_text(pdf_text) or ""
    code = extract_code_from_text(pdf_text) or ""

    # 日期
    notice_time = data.get("noticeSendTime", "")
    date_str = ""
    if notice_time:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", notice_time)
        if m:
            date_str = m.group(1)

    # 投标人 / 代理机构
    buyer = data.get("tenderBidder", "") or ""
    tender_agency = data.get("tenderAgency", "") or ""

    # 公告内容（从 PDF 提取）
    content = ""
    if pdf_text:
        # 清理 HTML 特殊字符
        clean_text = pdf_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        content = f"<div class=\"pdf-content\"><pre>{clean_text}</pre></div>"
    else:
        # 无 PDF，提供查看原文链接
        content = f"<div class=\"pdf-notice\"><p>公告全文需至原文页面查看</p></div>"

    source_url = DETAIL_URL_TPL.format(uuid=uuid)

    return {
        "id": md5(source_url)[:12],
        "title": title,
        "source": "招标投标公共服务平台",
        "industry": industry,
        "region": region,
        "method": method,
        "budget": budget,
        "date": date_str,
        "deadline": "",
        "buyer": buyer,
        "tenderAgency": tender_agency,
        "code": code,
        "sourceUrl": source_url,
        "content": content,
    }


async def crawl_with_playwright(
    spider: CEBPubPlaywrightSpider,
    existing_ids: set,
    new_bids: list,
    category_id: str = "88",
    start_date: str | None = None,
    end_date: str | None = None,
    max_pages: int = 500,
    max_items: int = 30,  # 每次爬取最大处理数（Playwright 较慢，控制数量）
):
    """主力爬虫：列表页（requests）+ 详情页（Playwright）"""
    cat_name = CATEGORIES.get(category_id, "全部")
    print(f"\n{'='*60}")
    print(f"分类: {cat_name} (categoryId={category_id})")
    print(f"日期范围: {start_date} ~ {end_date}")
    print(f"Playwright 深度爬取（最多 {max_items} 条）")
    print(f"{'='*60}")

    session = requests.Session()
    base_params = {"categoryId": category_id}
    if start_date:
        base_params["publishTimeStart"] = start_date
    if end_date:
        base_params["publishTimeEnd"] = end_date

    # Step 1: 收集列表页 UUID
    all_items = []
    for page_num in range(1, max_pages + 1):
        params = {**base_params, "page": str(page_num)}
        print(f"\n  列表页 {page_num}...", end="")
        items = crawl_list_page(session, params)
        if not items:
            print(" 无数据")
            break
        # 去重（已有 IDs）
        new_items = []
        all_existing = True
        for item in items:
            url_md5 = md5(item["sourceUrl"])
            if url_md5 not in existing_ids:
                all_existing = False
                new_items.append(item)
            else:
                pass  # 跳过已爬取的

        print(f" 新增 {len(new_items)}/{len(items)}")
        all_items.extend(new_items)

        if all_existing and page_num > 1:
            print("  → 后续均已爬取，提前结束")
            break

        if len(all_items) >= max_items:
            all_items = all_items[:max_items]
            print(f"  → 已达上限 {max_items} 条")
            break

        time.sleep(1)

    if not all_items:
        print("\n  无新增条目")
        return 0

    print(f"\n  共 {len(all_items)} 条待深度爬取")

    # Step 2: Playwright 深度爬取详情
    total_ok = 0
    for i, item in enumerate(all_items):
        uuid = item["uuid"]
        print(f"\n  [{i+1}/{len(all_items)}] {item['title'][:50]}...", end="")

        result = await spider.fetch_detail(uuid, session)

        if result and result.get("api_data"):
            bid = build_bid_from_api(
                uuid=uuid,
                api_data=result["api_data"],
                pdf_text=result.get("pdf_text", ""),
                title_from_list=item["title"],
                industry_list=item.get("industry_list", ""),
                region_list=item.get("region_list", ""),
                category_id=category_id,
            )
            new_bids.append(bid)
            existing_ids.add(md5(bid["sourceUrl"]))
            total_ok += 1
            print(f" ✓ {len(result.get('pdf_text', ''))}字")
        else:
            # 保底：使用列表页元数据
            print(f" ⚠ 详情失败，使用列表页数据")
            bid = {
                "id": item["id"],
                "title": item["title"],
                "source": "招标投标公共服务平台",
                "industry": extract_industry(item["title"], item.get("industry_list", "")),
                "region": extract_region(item.get("region_list", ""), item["title"]),
                "method": extract_method(item["title"]),
                "budget": "",
                "date": item["date"],
                "deadline": extract_deadline(item.get("deadline_td")),
                "buyer": "",
                "tenderAgency": "",
                "code": "",
                "sourceUrl": item["sourceUrl"],
                "content": "<div>公告全文未收录</div>",
            }
            new_bids.append(bid)
            existing_ids.add(md5(bid["sourceUrl"]))
            total_ok += 1

        # 每 10 条增量保存
        if len(new_bids) % 10 == 0:
            existing = load_existing_bids()
            interim = existing + new_bids
            interim.sort(key=lambda b: b.get("date", ""), reverse=True)
            save_bids(interim)

    print(f"\n  📊 汇总: 成功 {total_ok}, 跳过 {len(all_items) - total_ok}")
    return total_ok


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CEBPub Playwright 深度爬虫")
    parser.add_argument("--category", default="88", choices=list(CATEGORIES.keys()))
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--pages", type=int, default=500)
    parser.add_argument("--max-items", type=int, default=30,
                        help="最大深度处理数量（默认 30，Playwright 较慢）")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    start_date = args.start if args.start else seven_days_ago
    end_date = args.end if args.end else today

    print(f"🚀 CEBPub Playwright 深度爬虫启动")
    print(f"   日期: {start_date} ~ {end_date}")
    print(f"   分类: {CATEGORIES.get(args.category, '全部')}")
    print(f"   最大深度: {args.max_items} 条")

    existing_ids = load_existing_ids()
    existing_bids = load_existing_bids()
    print(f"   已有标讯: {len(existing_bids)} 条")

    if fitz is None:
        print("  ⚠ PyMuPDF 未安装，PDF 文本提取不可用")
    else:
        print(f"  ✓ PyMuPDF {fitz.__version__}")
    print(f"  ✓ Crypto DES（API 解密）")

    new_bids = []

    async def run():
        spider = CEBPubPlaywrightSpider(max_workers=3)
        try:
            await crawl_with_playwright(
                spider=spider,
                existing_ids=existing_ids,
                new_bids=new_bids,
                category_id=args.category,
                start_date=start_date,
                end_date=end_date,
                max_pages=args.pages,
                max_items=args.max_items,
            )
        finally:
            await spider.close()

    asyncio.run(run())

    # 合并并保存
    if new_bids:
        good_urls = {md5(b["sourceUrl"]) for b in existing_bids if is_good_content(b.get("content", ""))}
        filtered_new = [b for b in new_bids if md5(b["sourceUrl"]) not in good_urls]
        dropped = len(new_bids) - len(filtered_new)
        all_bids = existing_bids + filtered_new
        all_bids.sort(key=lambda b: b.get("date", ""), reverse=True)
        save_bids(all_bids)
        if dropped:
            print(f"  🛡️ 跳过 {dropped} 条已有真实内容的标讯")
        print(f"\n✅ 完成: 新增 {len(filtered_new)} 条, 总计 {len(all_bids)} 条")
    else:
        print("\n✅ 完成: 无新增数据")


if __name__ == "__main__":
    main()
