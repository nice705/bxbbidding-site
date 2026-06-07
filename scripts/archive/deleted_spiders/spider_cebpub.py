#!/usr/bin/env python3
"""
标讯宝 · 中国招标投标公共服务平台爬虫 (cebpubservice.com)

爬取策略：
  1. 遍历列表页（bulletin.cebpubservice.com）→ 获取 UUID、标题、日期等
  2. PDF 下载（record-pdf/{uuid}）→ PyMuPDF 解析文本
  3. MD5(sourceUrl) 去重，增量追加 data/bids.json

分类（categoryId）：
  88 全部 | 89 更正公告 | 90 中标结果 | 91 中标候选人 | 92 资格预审

时间范围：最近 7 天

运行：
  python3 scripts/spider_cebpub.py
  或指定分类：
  python3 scripts/spider_cebpub.py --category 90
  或指定日期：
  python3 scripts/spider_cebpub.py --start 2026-05-20 --end 2026-05-24
"""

import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# ── 配置 ──────────────────────────────────────────────────────────────
LIST_URL = "https://bulletin.cebpubservice.com/xxfbcmses/search/bulletin.html"
PDF_URL_TPL = "https://bulletin.cebpubservice.com/agency/api/agency-business/tenant-record/record-pdf/{uuid}"
DETAIL_URL_TPL = "https://ctbpsp.com/#/bulletinDetail?uuid={uuid}"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

CATEGORIES = {
    "88": "全部",
    "89": "更正公告",
    "90": "中标结果",
    "91": "中标候选人",
    "92": "资格预审",
}

CATEGORY_METHOD_MAP = {
    "89": "更正公告",
    "90": "中标结果",
    "91": "中标候选人",
    "92": "资格预审",
    "88": "",  # 从标题推断
}

# 请求配置
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

PDF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,image/webp,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.ctbpsp.com/",
}

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MIN_DELAY = 1.0
MAX_DELAY = 3.0
PAGE_SIZE = 15  # 列表页每页固定15条

# 行业关键词映射
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

# 省份关键词
PROVINCE_KEYWORDS = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "台湾", "广西", "内蒙古", "西藏", "宁夏", "新疆",
]


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


def safe_request(url: str, session: requests.Session, headers: dict = None, method: str = "GET", **kwargs) -> requests.Response | None:
    """带重试的安全请求"""
    if headers is None:
        headers = HEADERS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method.upper() == "GET":
                resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
            else:
                resp = session.post(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 404 or resp.status_code == 403:
                return None  # 页面不存在或被封，跳过
            else:
                print(f"  ⚠ HTTP {resp.status_code} {url[:80]} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"  ⚠ 请求失败: {e} (attempt {attempt})")
        if attempt < MAX_RETRIES:
            delay = 2 ** attempt
            time.sleep(delay)
    return None


def extract_industry(title: str, industry_from_list: str = "") -> str:
    """从标题和列表页行业字段推断行业"""
    if industry_from_list and industry_from_list not in ("其他", "", "不限"):
        # 列表页的行业信息一般更准确，直接透传
        if industry_from_list in INDUSTRY_KEYWORDS:
            return industry_from_list
        # 非标准行业名，先模糊匹配
        for ind in INDUSTRY_KEYWORDS:
            if ind in industry_from_list or industry_from_list in ind:
                return ind
        return industry_from_list  # 透传原始值
    # 从标题关键词匹配
    full_text = title
    for ind, kws in INDUSTRY_KEYWORDS.items():
        if any(kw in full_text for kw in kws):
            return ind
    return ""


def extract_region(region_from_list: str = "", title: str = "") -> str:
    """从列表页地区字段或标题中提取省份"""
    if region_from_list and region_from_list not in ("", "全国"):
        # 去掉【】括号
        region = region_from_list.strip("【】").strip()
        if region in PROVINCE_KEYWORDS:
            return region
    for prov in PROVINCE_KEYWORDS:
        if prov in title:
            return prov
    return ""


def extract_method(title: str, category_id: str) -> str:
    """从标题推断招标方式"""
    method = CATEGORY_METHOD_MAP.get(category_id, "")
    if method:
        return method

    # 从标题关键词推断
    method_patterns = [
        (r"公开招标", "公开招标"),
        (r"竞争性磋商", "竞争性磋商"),
        (r"竞争性谈判", "竞争性谈判"),
        (r"单一来源", "单一来源"),
        (r"询价|询比采购|询比公告", "询价"),
        (r"中标结果|中标公告", "中标公告"),
        (r"中标候选人", "中标候选人"),
        (r"更正公告|变更公告", "更正公告"),
        (r"资格预审", "资格预审"),
        (r"邀请招标", "邀请招标"),
        (r"谈判采购", "谈判采购"),
        (r"竞价公告|竞价", "竞价"),
        (r"比选", "比选"),
        (r"方案征集|征集公告", "方案征集"),
        (r"直接采购", "直接采购"),
        (r"招标公告", "公开招标"),
    ]
    for pat, name in method_patterns:
        if re.search(pat, title):
            return name
    return ""


def extract_deadline(td_element) -> str:
    """从开标时间 td 提取截止日期"""
    if not td_element:
        return ""
    text = td_element.get_text(strip=True)
    # 格式通常是 "加载中..." 或 "2026-05-29 14:00:00"
    # id 属性中可能包含时间
    td_id = td_element.get("id", "")
    if td_id and td_id != text and "加载" not in td_id and "openTime" not in td_id:
        # id 是日期时间字符串
        m = re.match(r"(\d{4}-\d{2}-\d{2})", td_id)
        if m:
            return m.group(1)
    # 从文本中提取
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    # 从 id 中提取（id 可能包含日期）
    m = re.search(r"(\d{4}-\d{2}-\d{2})", td_id)
    if m:
        return m.group(1)
    return ""


def extract_pdf_text(pdf_content: bytes) -> str:
    """使用 PyMuPDF 提取 PDF 文本"""
    if fitz is None:
        return ""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        texts = []
        for page in doc:
            text = page.get_text()
            if text and text.strip():
                texts.append(text.strip())
        doc.close()
        return "\n\n".join(texts)
    except Exception as e:
        print(f"    ⚠ PDF 解析失败: {e}")
        return ""


def extract_budget_from_text(text: str) -> str:
    """从文本中提取预算金额"""
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
            amt = m.group(1).replace(",", "").replace("，", "")
            return amt
    return ""


def extract_code_from_text(text: str) -> str:
    """从文本中提取项目编号"""
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


# ── 列表页爬取 ──────────────────────────────────────────────────────


def crawl_list_page(session: requests.Session, params: dict) -> list[dict]:
    """
    爬取单页列表，返回解析后的标讯条目列表（含元数据，不含 content）
    """
    items = []
    url = LIST_URL + "?" + urlencode(params)
    resp = safe_request(url, session)
    if resp is None:
        return items

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table_text")
    if not table:
        print(f"  ⚠ 未找到数据表格")
        return items

    rows = table.find_all("tr")
    for row in rows[1:]:  # 跳过表头
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        # --- 标题 & UUID ---
        title_cell = cells[0]
        link = title_cell.find("a")
        if not link:
            continue
        href = link.get("href", "")
        # 提取 UUID: javascript:urlOpen('{uuid}')
        uuid_match = re.search(r"urlOpen\('([a-f0-9\-]+)'\)", href)
        if not uuid_match:
            continue
        uuid_str = uuid_match.group(1)
        # 优先使用 title 属性（完整标题），回退到 link 文本
        title = link.get("title") or link.get_text(strip=True)
        title = re.sub(r"\s+", " ", title).strip()

        # --- 行业 ---
        industry_text = cells[1].get_text(strip=True)

        # --- 地区 ---
        region_text = cells[2].get_text(strip=True)

        # --- 来源渠道 ---
        source_channel = cells[3].get_text(strip=True)

        # --- 日期 ---
        date_text = cells[4].get_text(strip=True)

        # --- 开标时间 / 截止 ---
        deadline_td = cells[5]

        source_url = DETAIL_URL_TPL.format(uuid=uuid_str)
        bid_id = md5(source_url)

        item = {
            "id": bid_id[:12],
            "uuid": uuid_str,
            "title": title,
            "industry_list": industry_text,
            "region_list": region_text,
            "source_channel": source_channel,
            "date": date_text.strip(),
            "deadline_td": deadline_td,
            "sourceUrl": source_url,
        }
        items.append(item)

    # 检查是否有分页信息
    pagination = soup.find("div", class_="pagination")
    total_pages = 0
    if pagination:
        # 共<label>500</label>页
        page_label = pagination.find("label")
        if page_label:
            try:
                total_pages = int(page_label.get_text(strip=True))
            except ValueError:
                pass
        # 当前页码
        current_label = pagination.find_all("label")
        if len(current_label) >= 2:
            try:
                current_page = int(current_label[1].get_text(strip=True))
                print(f"  → 第 {current_page}/{total_pages} 页, 本页 {len(items)} 条")
            except ValueError:
                pass

    return items


def crawl(
    session: requests.Session,
    existing_ids: set,
    new_bids: list,
    category_id: str = "88",
    start_date: str | None = None,
    end_date: str | None = None,
    max_pages: int = 500,
):
    """
    主力爬虫函数
    """
    cat_name = CATEGORIES.get(category_id, "全部")
    print(f"\n{'='*60}")
    print(f"分类: {cat_name} (categoryId={category_id})")
    print(f"日期范围: {start_date} ~ {end_date}")
    print(f"{'='*60}")

    # 构建固定参数
    base_params = {
        "categoryId": category_id,
    }
    if start_date:
        base_params["publishTimeStart"] = start_date
    if end_date:
        base_params["publishTimeEnd"] = end_date

    total_new = 0
    total_skipped = 0
    total_pdf_ok = 0

    for page in range(1, max_pages + 1):
        params = {**base_params, "page": str(page)}
        print(f"\n  第 {page} 页...")

        items = crawl_list_page(session, params)
        if not items:
            print(f"  → 页面无数据，爬取结束")
            break

        # 检查是否所有项目都已存在（提前终止）
        all_existing = True
        for item in items:
            url_md5 = md5(item["sourceUrl"])
            if url_md5 not in existing_ids:
                all_existing = False
                break

        if all_existing and page > 1:
            print(f"  → 后续条目均已爬取过，提前结束")
            break

        # 处理每一条
        for item in items:
            url_md5 = md5(item["sourceUrl"])
            if url_md5 in existing_ids:
                total_skipped += 1
                continue

            # 日期过滤（二次确认）
            if start_date and item["date"]:
                if item["date"] < start_date:
                    existing_ids.add(url_md5)
                    total_skipped += 1
                    continue

            uuid_str = item["uuid"]
            title = item["title"]
            print(f"    · {title[:50]}...", end="")

            # 下载 PDF
            pdf_url = PDF_URL_TPL.format(uuid=uuid_str)
            pdf_resp = safe_request(pdf_url, session, headers=PDF_HEADERS)
            pdf_text = ""
            if pdf_resp and len(pdf_resp.content) > 1000:
                pdf_text = extract_pdf_text(pdf_resp.content)
                if pdf_text:
                    total_pdf_ok += 1

            # 构建 content —— 使用 PDF 文本包裹在 div 中
            if pdf_text and "页面访问提示" not in pdf_text[:50]:
                # 有实际内容的 PDF
                content = f"<div class=\"pdf-content\"><pre>{pdf_text}</pre></div>"
            elif pdf_text:
                # PDF 内容是暂停访问提示
                content = f"<div class=\"pdf-notice\"><pre>{pdf_text}</pre></div>"
            else:
                content = "<div>PDF内容为空</div>"

            # 从 PDF 文本中尝试提取额外字段
            budget = extract_budget_from_text(pdf_text)
            code = extract_code_from_text(pdf_text)

            # 构建标讯条目
            industry = extract_industry(title, item.get("industry_list", ""))
            region = extract_region(item.get("region_list", ""), title)
            method = extract_method(title, category_id)

            bid = {
                "id": item["id"],
                "title": title,
                "source": "招标投标公共服务平台",
                "industry": industry,
                "region": region,
                "method": method,
                "budget": budget,
                "date": item["date"],
                "deadline": extract_deadline(item["deadline_td"]),
                "buyer": "",
                "code": code,
                "sourceUrl": item["sourceUrl"],
                "content": content,
            }

            new_bids.append(bid)
            existing_ids.add(url_md5)
            total_new += 1
            print(f" ✓ PDF:{len(pdf_text)}字")
            # 每 50 条增量保存（只写最新批次）
            if total_new % 50 == 0:
                existing = load_existing_bids()
                batch = new_bids[-50:]
                interim = existing + batch
                interim.sort(key=lambda b: b.get("date", ""), reverse=True)
                save_bids(interim)

            # 请求间隔
            time.sleep(MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (hash(uuid_str) % 100) / 100)

        # 列表页间隔
        time.sleep(MIN_DELAY + (MAX_DELAY - MIN_DELAY) * (hash(str(page)) % 50) / 100)

    print(f"\n  📊 分类 {cat_name} 汇总: 新增 {total_new}, 跳过 {total_skipped}, PDF成功 {total_pdf_ok}")
    return total_new


# ── 主入口 ──────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="中国招标投标公共服务平台爬虫")
    parser.add_argument("--category", default="88", choices=list(CATEGORIES.keys()),
                        help="分类ID: 88全部 89更正 90中标 91候选人 92资格预审 (默认: 88)")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD (默认: 7天前)")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD (默认: 今天)")
    parser.add_argument("--pages", type=int, default=500, help="最大爬取页数 (默认: 500)")
    args = parser.parse_args()

    # 日期处理
    today = datetime.now().strftime("%Y-%m-%d")
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    start_date = args.start if args.start else seven_days_ago
    end_date = args.end if args.end else today

    print(f"🚀 招标投标公共服务平台爬虫启动")
    print(f"   日期范围: {start_date} ~ {end_date}")
    print(f"   分类: {CATEGORIES.get(args.category, '全部')} ({args.category})")

    # 加载已有数据
    existing_ids = load_existing_ids()
    existing_bids = load_existing_bids()
    print(f"   已有标讯: {len(existing_bids)} 条")

    if fitz is None:
        print("  ⚠ PyMuPDF 未安装，PDF文本提取将不可用")
    else:
        print(f"  ✓ PyMuPDF {fitz.__version__}")

    session = requests.Session()

    # 按分类爬取（默认88全部覆盖所有，也可以逐个分类爬取）
    new_bids = []
    crawl(
        session=session,
        existing_ids=existing_ids,
        new_bids=new_bids,
        category_id=args.category,
        start_date=start_date,
        end_date=end_date,
        max_pages=args.pages,
    )

    # 合并并保存（保护已有真实内容的标讯不被覆盖）
    if new_bids:
        good_urls = {md5(b["sourceUrl"]) for b in existing_bids if is_good_content(b.get("content", ""))}
        filtered_new = [b for b in new_bids if md5(b["sourceUrl"]) not in good_urls]
        dropped = len(new_bids) - len(filtered_new)
        all_bids = existing_bids + filtered_new
        save_bids(all_bids)
        if dropped:
            print(f"  🛡️ 跳过 {dropped} 条已有真实内容的标讯（防止覆盖）")
        print(f"\\n✅ 爬取完成: 新增 {len(filtered_new)} 条, 总计 {len(all_bids)} 条")
    else:
        print(f"\n✅ 爬取完成: 无新增数据")


if __name__ == "__main__":
    main()
