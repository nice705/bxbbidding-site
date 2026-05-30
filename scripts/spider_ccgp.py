#!/usr/bin/env python3
"""
标讯宝 · 中国政府采购网爬虫 (ccgp.gov.cn)

爬取策略：
  1. 遍历所有频道（中央级 + 地方级 × 子分类）
  2. 列表页 index.htm ~ index_N.htm（最多25页）
  3. 详情页解析结构化字段
  4. MD5(sourceUrl) 去重，增量追加 data/bids.json

反爬对策：
  - UA 模拟浏览器
  - 请求间隔 1-3 秒
  - 超时重试（最多3次）

运行：
  python3 scripts/spider_ccgp.py
  或指定日期范围：
  python3 scripts/spider_ccgp.py --start 2026-05-20 --end 2026-05-24
"""

import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# 导入产品提取器
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.product_extractor import extract_products

# ── 配置 ──────────────────────────────────────────────────────────────
BASE_URL = "http://www.ccgp.gov.cn"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

# 中央级 + 地方级所有子分类频道
CHANNELS = []
# 中央级
CENTER_CATS = ["gkzb", "zbgg", "gzgg", "jzxcs", "jzxjz", "xjgg", "qtgg", "dyly", "jzxtp", "zlcg"]
for cat in CENTER_CATS:
    CHANNELS.append(f"/cggg/zygg/{cat}/")
# 地方级
LOCAL_CATS = ["gkzb", "zbgg", "gzgg", "jzxcs", "jzxjz", "xjgg", "qtgg", "dyly", "jzxtp", "zlcg"]
for cat in LOCAL_CATS:
    CHANNELS.append(f"/cggg/dfgg/{cat}/")

# 子分类 → 采购方式映射
METHOD_MAP = {
    "gkzb": "公开招标",
    "zbgg": "中标公告",
    "gzgg": "更正公告",
    "jzxcs": "竞争性磋商",
    "jzxjz": "竞争性谈判",
    "xjgg": "询价公告",
    "qtgg": "其他公告",
    "dyly": "单一来源",
    "jzxtp": "竞争性谈判",
    "zlcg": "战略采购",
}

# 请求配置
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "http://www.ccgp.gov.cn/",
}
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MIN_DELAY = 1.0
MAX_DELAY = 3.0

# ── 工具函数 ──────────────────────────────────────────────────────────


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def is_good_content(content: str) -> bool:
    """判断内容是否真实有效（非空、非屏蔽、有长度）"""
    if not content or len(content) <= 100:
        return False
    blocked_keywords = ['页面访问提示', '暂停访问', 'PDF 文件']
    return not any(kw in content for kw in blocked_keywords)


def load_existing_ids() -> set:
    """加载已存在的 sourceUrl MD5 集合，用于去重"""
    if not os.path.exists(DATA_FILE):
        return set()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {md5(b["sourceUrl"]) for b in data.get("bids", [])}
    except (json.JSONDecodeError, KeyError):
        return set()


def load_existing_bids() -> list:
    """加载完整 bids 列表"""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("bids", [])
    except (json.JSONDecodeError, KeyError):
        return []


def save_bids(bids: list):
    """写入 bids.json，保持结构完整"""
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


def safe_request(url: str, session: requests.Session) -> requests.Response | None:
    """带重试的安全请求"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 404:
                return None  # 页面不存在，跳过
            else:
                print(f"  ⚠ HTTP {resp.status_code} {url} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {e} (attempt {attempt})")
        if attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
    return None


def extract_text(soup: BeautifulSoup, selector: str) -> str:
    """安全提取文本"""
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else ""


# ── 详情页解析 ──────────────────────────────────────────────────────


def parse_detail(channel_url: str, page_url: str, html: str, channel: str) -> dict | None:
    """
    解析详情页 HTML，返回标讯字典。
    """
    soup = BeautifulSoup(html, "html.parser")

    # -- 标题 --
    title = ""
    h2 = soup.select_one("h2")
    if h2:
        title = h2.get_text(strip=True)
    if not title:
        title_tag = soup.select_one("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
    if not title:
        # 从其他位置提取
        title = extract_text(soup, "h1")

    if not title or title == "中国政府采购网":
        return None  # 无效页面

    # 清理标题
    title = re.sub(r"\s+", " ", title).strip()

    # -- 采购方式 --
    method = METHOD_MAP.get(channel.split("/")[-2] if channel.endswith("/") else channel.split("/")[-1], "")
    if not method:
        # 从正文提取
        method_text = extract_text(soup, "p:contains('采购方式')")
        if method_text:
            m = re.search(r"采购方式[：:]\s*(.+)", method_text)
            if m:
                method = m.group(1).strip()

    # -- 项目编号 --
    code = ""
    code_text = extract_text(soup, "p:contains('项目编号')")
    if code_text:
        m = re.search(r"项目编号[：:]\s*(\S+)", code_text)
        if m:
            code = m.group(1).strip()
    if not code:
        # 从详情页找
        match = re.search(r"项目编号[：:]?\s*([^\s<]+)", html[:2000])
        if match:
            code = match.group(1).strip()

    # -- 预算 --
    budget = ""
    budget_patterns = [
        r"预算金额[：:]?\s*([0-9,，.]+)\s*万元",
        r"预算金额[：:]?\s*([0-9,，.]+)\s*元",
        r"预算[：:]?\s*([0-9,，.]+)\s*万元",
        r"项目预算[：:]?\s*([0-9,，.]+)\s*万元",
    ]
    for pat in budget_patterns:
        m = re.search(pat, html[:5000])
        if m:
            amt = m.group(1).replace(",", "").replace("，", "")
            try:
                float(amt)
                budget = amt
                break
            except ValueError:
                continue

    # -- 采购人 --
    buyer = ""
    # 格式1: 采购人信息 → 名 称：xxx
    buyer_m = re.search(
        r'采购人信息[^<]*</p>\s*<p>[^<]*名\s*[称稱][：:]\s*([^<>\n\u3000]{2,60})',
        html[:8000]
    )
    if buyer_m:
        buyer = buyer_m.group(1).strip()
        buyer = re.sub(r'\u3000', '', buyer).strip()
    # 格式2: 采购方/单位：xxx
    if not buyer:
        buyer_texts = ["采购人", "采购单位", "采购方", "招标人", "招标单位", "业主"]
        for bt in buyer_texts:
            for p in soup.select("p"):
                text = p.get_text(strip=True)
                if bt in text:
                    m = re.search(rf"{bt}[：:]\s*([^<\\n]{{2,40}})", text)
                    if m:
                        candidate = m.group(1).strip()
                        if len(candidate) >= 2 and not candidate.startswith("("):
                            buyer = candidate
                            break
            if buyer:
                break
    # 格式3: 通用 名 称：xxx（表格中的第一处）
    if not buyer:
        buyer_m2 = re.search(
            r'名\s*[称稱][：:]\s*([^<>\n\u3000]{2,60})',
            html[:5000]
        )
        if buyer_m2:
            candidate = buyer_m2.group(1).strip()
            candidate = re.sub(r'\u3000', '', candidate).strip()
            if candidate and len(candidate) >= 2:
                buyer = candidate

    # -- 日期 --
    date_str = ""
    # 从 URL 中提取 tYYYYMMDD
    url_match = re.search(r"t(\d{4})(\d{2})(\d{2})_", page_url)
    if url_match:
        date_str = f"{url_match.group(1)}-{url_match.group(2)}-{url_match.group(3)}"

    # -- 截止时间 --
    deadline = ""
    deadline_patterns = [
        r"递交投标文件[^。]*?(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"提交投标文件[^。]*?(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"开标时间[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"投标截止[^。]*?(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"截止时间[：:]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
    ]
    for pat in deadline_patterns:
        m = re.search(pat, html)
        if m:
            deadline = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            break

    # -- 地域 --
    region = ""
    province_keywords = [
        "北京", "天津", "上海", "重庆",
        "河北", "山西", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西", "山东",
        "河南", "湖北", "湖南", "广东", "海南",
        "四川", "贵州", "云南", "陕西", "甘肃", "青海",
        "台湾", "广西", "内蒙古", "西藏", "宁夏", "新疆",
        "兵团",
    ]
    # 1. 从 content 中的地址字段提取
    addr_match = re.search(r'地址[：:]\s*([^<>\n]{2,60})', html[:8000])
    if addr_match:
        addr = addr_match.group(1)
        for prov in province_keywords:
            if prov in addr:
                region = prov
                break
    # 2. 从 buyer 提取
    if not region and buyer:
        for prov in province_keywords:
            if prov in buyer:
                region = prov
                break
    # 3. 从 title 提取
    if not region:
        for prov in province_keywords:
            if prov in title:
                region = prov
                break
    # 4. 从 /dfgg/ 页面的 URL 路径提取（省份缩写映射）
    if not region and '/dfgg/' in page_url:
        m = re.search(r'/dfgg/([a-z]+)/', page_url)
        if m:
            abbr = m.group(1).lower()
            region_map = {
                'bj': '北京', 'sh': '上海', 'tj': '天津', 'cq': '重庆',
                'he': '河北', 'sx': '山西', 'ln': '辽宁', 'jl': '吉林', 'hlj': '黑龙江',
                'js': '江苏', 'zj': '浙江', 'ah': '安徽', 'fj': '福建', 'jx': '江西', 'sd': '山东',
                'hn': '河南', 'hb': '湖北', 'gd': '广东', 'gx': '广西',
                'sc': '四川', 'gz': '贵州', 'yn': '云南', 'xz': '西藏',
                'gs': '甘肃', 'qh': '青海', 'nx': '宁夏', 'xj': '新疆', 'nm': '内蒙古',
            }
            for a, prov in region_map.items():
                if a == abbr or abbr.startswith(a) or a.startswith(abbr):
                    region = prov
                    break

    # -- 行业 --
    industry = ""
    industry_keywords = {
        "医疗": ["医院", "医疗", "药品", "医用", "CT", "核磁", "超声", "救护", "手术", "卫生"],
        "IT信息化": ["信息化", "软件", "系统", "平台", "网络", "服务器", "交换机", "计算机", "机房", "数据"],
        "工程建设": ["工程", "施工", "建设", "装修", "修缮", "道路", "桥梁", "市政", "建筑"],
        "教育科研": ["学校", "学院", "大学", "教育", "教学", "教室", "图书", "科研"],
        "环保": ["环保", "环卫", "垃圾", "污水", "环境", "绿化"],
        "安防": ["安防", "监控", "门禁", "消防", "安保", "安全"],
        "物业后勤": ["物业", "食堂", "餐饮", "保洁", "保安", "后勤", "劳务"],
        "交通": ["交通", "车辆", "公交", "出租车", "运输", "物流"],
        "农林牧渔": ["农业", "林业", "畜牧", "渔业", "种子", "化肥", "农药"],
        "文体": ["体育", "文化", "会展", "展览", "演出"],
    }
    full_text = title + " " + (buyer or "")
    for ind, kws in industry_keywords.items():
        if any(kw in full_text for kw in kws):
            industry = ind
            break

    # -- 内容 --
    content = html
    # 尝试只提取正文区域
    notice = soup.select_one("#noticeArea, .protect, .vF_detail_content, .main-content")
    if notice:
        content = str(notice)
    else:
        body = soup.select_one("body")
        if body:
            # 去掉页头页脚
            for el in body.select("script, style, iframe, .header, .footer, .top, .bottom"):
                el.decompose()
            content = str(body)

    return {
        "id": md5(page_url)[:12],
        "title": title,
        "source": "政府采购网",
        "industry": industry,
        "region": region,
        "method": method,
        "budget": budget,
        "date": date_str,
        "deadline": deadline,
        "buyer": buyer,
        "code": code,
        "sourceUrl": page_url,
        "content": content,
    }


# ── 列表页爬取 ──────────────────────────────────────────────────────


def crawl_channel(
    session: requests.Session,
    channel: str,
    existing_ids: set,
    new_bids: list,
    date_filter: tuple[str, str] | None = None,
    max_pages: int = 25,
):
    """
    爬取单个频道的所有列表页。
    channel: 例如 /cggg/zygg/gkzb/
    """
    full_url = urljoin(BASE_URL, channel)
    print(f"\n{'='*60}")
    print(f"频道: {channel}  →  {full_url}")
    print(f"{'='*60}")

    for page_idx in range(max_pages):
        if page_idx == 0:
            list_url = urljoin(full_url, "index.htm")
        else:
            list_url = urljoin(full_url, f"index_{page_idx}.htm")

        print(f"\n  第 {page_idx + 1} 页: {list_url}")

        resp = safe_request(list_url, session)
        if resp is None:
            print(f"  → 已无更多页面")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # 提取详情页链接（仅限 /cggg/ 下公告页）
        links = []
        for a in soup.select("a[href*='.htm']"):
            href = a.get("href", "")
            if re.search(r"t\d{8}_\w+\.htm", href):
                full_detail_url = urljoin(BASE_URL, href) if href.startswith("/") else urljoin(list_url, href)
                if "/cggg/" not in full_detail_url:
                    continue
                links.append(full_detail_url)

        if not links:
            # 也可能是其他选择器
            for a in soup.select("ul.list-a a, div.list a, table a"):
                href = a.get("href", "")
                if ".htm" in href:
                    full_detail_url = urljoin(BASE_URL, href) if href.startswith("/") else urljoin(list_url, href)
                    links.append(full_detail_url)

        links = list(set(links))  # 去重
        print(f"  → 发现 {len(links)} 个详情页链接")

        if not links:
            # 检查是否没有更多页面了
            body_text = soup.get_text(strip=True)
            if "暂无信息" in body_text or "没有数据" in body_text or "无相关" in body_text:
                print(f"  → 频道无更多数据")
                break
            print(f"  ⚠ 未找到详情链接，继续下一页")
            continue

        # 爬取每个详情页
        for detail_url in links:
            url_md5 = md5(detail_url)
            if url_md5 in existing_ids:
                continue  # 已存在，跳过

            # 日期过滤
            if date_filter:
                m = re.search(r"t(\d{4})(\d{2})(\d{2})_", detail_url)
                if m:
                    detail_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                    if detail_date < date_filter[0] or detail_date > date_filter[1]:
                        existing_ids.add(url_md5)  # 标记为已处理，避免重复检查
                        continue

            print(f"    · 详情: {detail_url}")

            detail_resp = safe_request(detail_url, session)
            if detail_resp is None:
                existing_ids.add(url_md5)
                continue

            bid = parse_detail(channel, detail_url, detail_resp.text, channel)
            if bid:
                # 提取产品标签
                products = extract_products(bid.get("title", ""), bid.get("content", ""))
                if products:
                    bid["products"] = products
                new_bids.append(bid)
                existing_ids.add(url_md5)
                print(f"      ✓ {bid['title'][:40]}...")
                # 每 50 条增量保存一次（只写最新批次，避免重复）
                if len(new_bids) % 50 == 0:
                    existing = load_existing_bids()
                    batch = new_bids[-50:]
                    interim = existing + batch
                    interim.sort(key=lambda b: b.get("date", ""), reverse=True)
                    save_bids(interim)
            else:
                existing_ids.add(url_md5)
                print(f"      ⚠ 解析失败")

            # 请求间隔
            time.sleep(MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (hash(detail_url) % 100) / 100)

        # 列表页间隔
        time.sleep(MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (hash(list_url) % 50) / 100)


def crawl_search(
    session: requests.Session,
    existing_ids: set,
    new_bids: list,
    start_date: str | None = None,
    end_date: str | None = None,
    max_pages: int = 50,
):
    """
    使用搜索接口批量爬取（备选方案，速度更快）
    搜索接口：search.ccgp.gov.cn/bxsearch
    """
    search_url = "http://search.ccgp.gov.cn/bxsearch"
    today = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = today

    print(f"\n{'='*60}")
    print(f"搜索接口: {search_url}")
    print(f"日期范围: {start_date} ~ {end_date}")
    print(f"{'='*60}")

    page = 1
    while page <= max_pages:
        params = {
            "searchtype": "1",
            "page_index": str(page),
            "bidType": "0",
            "kw": "",
            "start_time": start_date,
            "end_time": end_date,
            "timeType": "0",
            "displayZone": "",
            "zoneId": "",
            "pppStatus": "0",
            "agentName": "",
        }
        print(f"\n  搜索第 {page} 页...")
        try:
            resp = session.get(
                search_url,
                params=params,
                headers={**HEADERS, "Referer": "http://www.ccgp.gov.cn/"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                print(f"  ⚠ HTTP {resp.status_code}, 停止搜索")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.select("a[href*='.htm']"):
                href = a.get("href", "")
                if re.search(r"t\d{8}_\w+\.htm", href):
                    full_url = urljoin("http://www.ccgp.gov.cn", href) if href.startswith("/") else href
                    links.append(full_url)

            links = list(set(links))
            print(f"  → 发现 {len(links)} 条结果")

            if not links:
                print(f"  → 无更多结果")
                break

            for detail_url in links:
                url_md5 = md5(detail_url)
                if url_md5 in existing_ids:
                    continue

                print(f"    · 详情: {detail_url}")
                detail_resp = safe_request(detail_url, session)
                if detail_resp is None:
                    existing_ids.add(url_md5)
                    continue

                channel_path = ""
                path_match = re.search(r"(/cggg/\w+/\w+/)", detail_url)
                if path_match:
                    channel_path = path_match.group(1)

                bid = parse_detail(channel_path, detail_url, detail_resp.text, channel_path)
                if bid:
                    new_bids.append(bid)
                    existing_ids.add(url_md5)
                    print(f"      ✓ {bid['title'][:40]}...")
                    # 每 50 条增量保存（只写最新批次）
                    if len(new_bids) % 50 == 0:
                        existing = load_existing_bids()
                        batch = new_bids[-50:]
                        interim = existing + batch
                        interim.sort(key=lambda b: b.get("date", ""), reverse=True)
                        save_bids(interim)
                else:
                    existing_ids.add(url_md5)
                    print(f"      ⚠ 解析失败")

                time.sleep(3 + (hash(detail_url) % 3))  # 搜索接口频率限制更严格

            page += 1
            time.sleep(3)  # 搜索接口分页间隔

        except requests.RequestException as e:
            print(f"  ⚠ 搜索异常: {e}")
            break


def main():
    import argparse

    parser = argparse.ArgumentParser(description="中国政府采购网爬虫")
    parser.add_argument("--method", choices=["channel", "search", "all"], default="channel",
                        help="爬取方式: channel=遍历频道, search=搜索接口, all=两者")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--channels", nargs="+", help="指定频道路径 (例如 /cggg/zygg/gkzb/)")
    parser.add_argument("--max-pages", type=int, default=25, help="每个频道最大页数 (默认25)")
    args = parser.parse_args()

    print("=" * 60)
    print("  标讯宝 · 中国政府采购网爬虫")
    print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 加载已有数据
    existing_ids = load_existing_ids()
    existing_bids = load_existing_bids()
    new_bids = []
    print(f"  已有数据: {len(existing_bids)} 条标讯, {len(existing_ids)} 个去重ID")

    session = requests.Session()

    date_filter = None
    if args.start and args.end:
        date_filter = (args.start, args.end)

    channels_to_crawl = args.channels if args.channels else CHANNELS

    if args.method in ("channel", "all"):
        for channel in channels_to_crawl:
            try:
                crawl_channel(
                    session, channel, existing_ids, new_bids,
                    date_filter=date_filter, max_pages=args.max_pages,
                )
            except Exception as e:
                print(f"  ❌ 频道 {channel} 爬取失败: {e}")
                traceback.print_exc()

    if args.method in ("search", "all"):
        try:
            crawl_search(
                session, existing_ids, new_bids,
                start_date=args.start, end_date=args.end,
                max_pages=args.max_pages * 2,
            )
        except Exception as e:
            print(f"  ❌ 搜索爬取失败: {e}")
            traceback.print_exc()

    # 合并并保存（保护已有真实内容的标讯不被覆盖）
    if new_bids:
        good_urls = {md5(b["sourceUrl"]) for b in existing_bids if is_good_content(b.get("content", ""))}
        filtered_new = [b for b in new_bids if md5(b["sourceUrl"]) not in good_urls]
        dropped = len(new_bids) - len(filtered_new)
        all_bids = existing_bids + filtered_new
        # 按日期降序排列
        all_bids.sort(key=lambda b: b.get("date", ""), reverse=True)
        save_bids(all_bids)
        if dropped:
            print(f"  🛡️ 跳过 {dropped} 条已有真实内容的标讯（防止覆盖）")
        print(f"\\n{'='*60}")
        print(f"  爬取完成: 新增 {len(filtered_new)} 条, 共 {len(all_bids)} 条")
        print(f"{'='*60}")
    else:
        print(f"\n  无新增标讯（已是最新）")


if __name__ == "__main__":
    main()
