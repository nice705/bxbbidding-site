#!/usr/bin/env python3
"""
标讯宝 · 爬虫共享模块

所有爬虫共享：数据 IO、去重、网络请求、行业/省份推断。
"""

import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from scripts.spider_proxy import (
    proxy_get,
    proxy_fetch,
    ProxyResponse,
    is_blocked_domain,
    BLOCKED_DOMAINS,
)

# ── 路径 ────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

# ── 请求默认配置 ─────────────────────────────────
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3

# ── 行业关键词（用于从标题推断行业） ──────────────
INDUSTRY_KEYWORDS = {
    "医疗": ["医院", "医疗", "药品", "医用", "CT", "核磁", "超声", "救护", "手术",
             "卫生", "临床", "医药", "医疗器械", "同仁医院", "人民医院", "疾控",
             "门诊", "康复", "护理", "病房", "消毒", "防疫", "急救", "体检"],
    "IT信息化": ["信息化", "软件", "系统", "平台", "网络", "服务器", "交换机",
               "计算机", "机房", "数据", "IT", "互联网", "数字化", "智能",
               "AI", "物联网", "电信", "代码开发", "信息系统", "云服务",
               "大数据", "网络安全", "ERP", "CRM", "OA"],
    "工程建设": ["工程", "施工", "建设", "装修", "修缮", "道路", "桥梁", "市政",
               "建筑", "改造", "维修", "加固", "通风工程", "消防改造", "土建",
               "钢结构", "混凝土", "给排水", "暖通"],
    "教育科研": ["学校", "学院", "大学", "教育", "教学", "教室", "图书", "科研",
               "培训", "教材", "实验", "实训", "图书馆", "体育馆", "学术"],
    "环保环卫": ["环保", "环卫", "垃圾", "污水", "环境", "绿化", "清洁", "保洁",
               "环卫车辆", "节能", "碳排放", "污水处理", "垃圾分类", "生态"],
    "安防消防": ["安防", "监控", "门禁", "消防", "安保", "安全", "报警", "摄像头",
               "人脸识别", "安检", "防盗", "防火"],
    "物业后勤": ["物业", "食堂", "餐饮", "保安", "后勤", "劳务", "服务", "外包",
               "租赁服务", "保洁服务", "食堂食材", "配送服务"],
    "交通运输": ["交通", "车辆", "公交", "出租车", "运输", "物流", "航运", "铁路",
               "公路", "塔式起重机", "推土机", "叉车", "货车", "汽车"],
    "房屋建筑": ["房屋建筑", "住宅", "房地产", "商品房", "安置房", "公租房"],
    "农林牧渔": ["农业", "林业", "畜牧", "渔业", "种子", "化肥", "农药", "农田",
               "水利", "灌溉", "水产", "养殖", "种植"],
    "文体旅游": ["体育", "文化", "会展", "展览", "演出", "旅游", "酒店", "博物馆",
               "体育馆", "剧院", "景区"],
    "机械设备": ["设备", "机械", "机电", "电气", "仪器", "仪表", "制造",
               "变压器", "配电柜", "柴油发电机组", "压缩机", "泵阀"],
    "能源电力": ["电力", "能源", "光伏", "风电", "太阳能", "电网", "供电", "配电",
               "发电", "铝业", "百河铝业", "变电站", "输电", "核电", "水电"],
}

# ── 省份关键词 ────────────────────────────────────
PROVINCE_KEYWORDS = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "台湾", "广西", "内蒙古", "西藏", "宁夏", "新疆",
]

# ── 工具函数 ──────────────────────────────────────


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def is_good_content(content: str, min_len: int = 100) -> bool:
    """判断内容是否真实有效"""
    if not content or len(content) <= min_len:
        return False
    blocked = ['页面访问提示', '暂停访问', 'PDF 文件', '502 Bad Gateway',
               '504 Gateway Time-out', '403 Forbidden', '404 Not Found']
    return not any(kw in content for kw in blocked)


def load_existing_ids() -> set:
    """加载已存在的 sourceUrl MD5 集合"""
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
    """写入 bids.json"""
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
    print(f"  ✓ 写入 {len(bids)} 条标讯 → {DATA_FILE} (今日 {today_count} 条)")


def append_bids(new_bids: list, source_name: str):
    """增量合并新标讯（去重），写入数据文件"""
    existing = load_existing_bids()
    existing_ids = {md5(b["sourceUrl"]) for b in existing if b.get("sourceUrl")}

    added = 0
    skipped = 0
    for bid in new_bids:
        if not bid.get("sourceUrl"):
            continue
        bid_id = md5(bid["sourceUrl"])
        if bid_id not in existing_ids:
            # 补默认字段
            bid.setdefault("id", bid_id[:12])
            bid.setdefault("source", source_name)
            bid.setdefault("industry", "")
            bid.setdefault("region", "")
            bid.setdefault("method", "")
            bid.setdefault("budget", "")
            bid.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
            bid.setdefault("deadline", "")
            bid.setdefault("buyer", "")
            bid.setdefault("code", "")
            bid.setdefault("products", [])
            existing.append(bid)
            existing_ids.add(bid_id)
            added += 1
        else:
            skipped += 1

    print(f"  {source_name}: +{added} 新增, {skipped} 去重跳过")
    save_bids(existing)


# ── 网络请求 ──────────────────────────────────────


def safe_request(
    url: str,
    session: requests.Session = None,
    headers: dict = None,
    method: str = "GET",
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    use_proxy: Optional[bool] = None,
    **kwargs,
) -> Optional[requests.Response]:
    """
    带重试的安全 HTTP 请求。

    对于被阻断的域名，自动通过 Cloudflare Pages 代理路由。
    可通过 use_proxy 参数控制:
      - True:  强制使用代理
      - False: 强制直连
      - None:  自动判断（默认）
    """
    # ── 判断是否使用代理 ──
    should_proxy = False
    if use_proxy is True:
        should_proxy = True
    elif use_proxy is None:
        should_proxy = is_blocked_domain(url)

    # ── 通过代理路由 ──
    if should_proxy:
        return _safe_request_proxy(url, method=method, headers=headers, timeout=timeout, retries=retries)

    # ── 直连 ──
    if session is None:
        session = requests.Session()
    if headers is None:
        headers = DEFAULT_HEADERS.copy()

    for attempt in range(1, retries + 1):
        try:
            if method.upper() == "GET":
                resp = session.get(url, headers=headers, timeout=timeout, **kwargs)
            else:
                resp = session.post(url, headers=headers, timeout=timeout, **kwargs)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (404, 410):
                return None  # 不存在，跳过
            else:
                print(f"  ⚠ HTTP {resp.status_code} {url[:100]} (try {attempt})")
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {e} (try {attempt})")
        if attempt < retries:
            time.sleep(2 ** attempt)
    return None


def _safe_request_proxy(
    url: str,
    method: str = "GET",
    headers: dict = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Optional[ProxyResponse]:
    """通过 CF Pages 代理发送请求"""
    print(f"  🌐 通过 CF 代理: {url[:100]}")
    from scripts.spider_proxy import proxy_fetch

    return proxy_fetch(url, method=method, timeout=timeout, retries=retries)


def random_delay(min_s: float = 1.0, max_s: float = 3.0):
    """随机延时，避免反爬"""
    time.sleep(random.uniform(min_s, max_s))


# ── 字段提取 ──────────────────────────────────────


def extract_text(soup: BeautifulSoup, selector: str) -> str:
    """安全提取文本"""
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else ""


def extract_industry(title: str, industry_from_list: str = "") -> str:
    """从标题推断行业"""
    if industry_from_list and industry_from_list not in ("其他", "", "不限"):
        if industry_from_list in INDUSTRY_KEYWORDS:
            return industry_from_list
        for ind in INDUSTRY_KEYWORDS:
            if ind in industry_from_list or industry_from_list in ind:
                return ind
        return industry_from_list
    for ind, kws in INDUSTRY_KEYWORDS.items():
        if any(kw in title for kw in kws):
            return ind
    return ""


def extract_region(region_from_list: str = "", title: str = "") -> str:
    """从标题提取省份"""
    if region_from_list and region_from_list not in ("", "全国"):
        region = region_from_list.strip("【】").strip()
        if region in PROVINCE_KEYWORDS:
            return region
    for prov in PROVINCE_KEYWORDS:
        if prov in title:
            return prov
    return ""


def extract_budget(html: str, max_scan: int = 5000) -> str:
    """从 HTML 中提取预算金额（万元）"""
    patterns = [
        r"预算金额[：:]?\s*([0-9,，.]+)\s*万元",
        r"预算金额[：:]?\s*([0-9,，.]+)\s*元",
        r"预算[：:]?\s*([0-9,，.]+)\s*万元",
        r"项目预算[：:]?\s*([0-9,，.]+)\s*万元",
        r"最高限价[：:]?\s*([0-9,，.]+)\s*万元",
        r"采购预算[：:]?\s*([0-9,，.]+)\s*万元",
    ]
    scan = html[:max_scan]
    for pat in patterns:
        m = re.search(pat, scan)
        if m:
            amt = m.group(1).replace(",", "").replace("，", "").strip()
            try:
                float(amt)
                return amt
            except ValueError:
                pass
    return ""


def extract_code(html: str) -> str:
    """从 HTML 提取项目编号"""
    m = re.search(r"项目编号[：:]?\s*([^\s<,，]+)", html[:3000])
    return m.group(1).strip() if m else ""


def extract_deadline(html: str) -> str:
    """从 HTML 提取截止时间"""
    patterns = [
        r"提交投标文件截止时间[：:]?\s*(\d{4}年\d{2}月\d{2}日)",
        r"投标截止时间[：:]?\s*(\d{4}年\d{2}月\d{2}日)",
        r"开标时间[：:]?\s*(\d{4}年\d{2}月\d{2}日)",
        r"响应文件提交截止时间[：:]?\s*(\d{4}年\d{2}月\d{2}日)",
        r"于\s*(\d{4}年\d{2}月\d{2}日)\s*前提交",
    ]
    for pat in patterns:
        m = re.search(pat, html[:5000])
        if m:
            return m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
    return ""


def make_bid_item(
    title: str,
    source_url: str,
    source_name: str,
    content: str = "",
    industry: str = "",
    region: str = "",
    method: str = "",
    budget: str = "",
    date: str = "",
    deadline: str = "",
    buyer: str = "",
    code: str = "",
    products: list = None,
) -> dict:
    """构造标准标讯字典"""
    if not title:
        title = ""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    item = {
        "id": md5(source_url)[:12] if source_url else "",
        "title": title.strip(),
        "source": source_name,
        "industry": industry or extract_industry(title),
        "region": region or extract_region(region_from_list="", title=title),
        "method": method,
        "budget": budget,
        "date": date,
        "deadline": deadline,
        "buyer": buyer,
        "code": code,
        "sourceUrl": source_url,
        "content": content,
        "products": products or [],
    }
    return item
