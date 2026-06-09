#!/usr/bin/env python3
"""
标讯宝 · cebpub 批量高速爬虫（全行业全覆盖版）

策略：
  1. 只爬列表页元数据（标题/日期/地区/行业），跳过 PDF 下载
  2. 多分类并行：89, 90, 91, 92 全部覆盖
  3. 高速爬取：无 PDF 延迟，单页 < 0.5s
  4. 增量写入：只追加新数据

目标：单次运行 10,000+ 条
"""

import hashlib, json, os, re, sys, time, traceback
from datetime import datetime, timedelta
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

LIST_URL = "https://bulletin.cebpubservice.com/xxfbcmses/search/bulletin.html"
DETAIL_URL_TPL = "https://ctbpsp.com/#/bulletinDetail?uuid={uuid}"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids-cebpub.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bulletin.cebpubservice.com/",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
PAGE_SIZE = 15
PAGE_DELAY = 0.15  # 页间延迟（秒）
CONCURRENT = 5     # 并发页数（快5倍）

CATEGORIES = {
    "89": "更正公告",
    "90": "中标结果",
    "91": "中标候选人",
    "92": "资格预审",
}

# 行业关键词
INDUSTRY_KEYWORDS = {
    "医疗": ["医院","医疗","药品","医用","CT","核磁","超声","救护","手术","卫生","临床","医药","医疗器械","疾控"],
    "IT信息化": ["信息化","软件","系统","平台","网络","服务器","交换机","计算机","机房","数据","IT","互联网","数字化","智能","AI","物联网","电信","代码开发"],
    "工程建设": ["工程","施工","建设","装修","修缮","道路","桥梁","市政","建筑","改造","维修","加固"],
    "教育科研": ["学校","学院","大学","教育","教学","教室","图书","科研","培训","教材"],
    "环保环卫": ["环保","环卫","垃圾","污水","环境","绿化","清洁","保洁","节能"],
    "安防消防": ["安防","监控","门禁","消防","安保","安全","报警"],
    "物业后勤": ["物业","食堂","餐饮","保安","后勤","劳务","服务","外包","租赁"],
    "交通运输": ["交通","车辆","公交","出租车","运输","物流","航运","铁路","公路"],
    "农林牧渔": ["农业","林业","畜牧","渔业","种子","化肥","农药","农田","水利"],
    "文体旅游": ["体育","文化","会展","展览","演出","旅游","酒店"],
    "机械设备": ["设备","机械","机电","电气","仪器","仪表","制造","变压器","配电柜"],
    "能源电力": ["电力","能源","光伏","风电","太阳能","电网","供电","配电","发电"],
}

PROVINCE_KEYWORDS = [
    "北京","天津","上海","重庆",
    "河北","山西","辽宁","吉林","黑龙江",
    "江苏","浙江","安徽","福建","江西","山东",
    "河南","湖北","湖南","广东","海南",
    "四川","贵州","云南","陕西","甘肃","青海",
    "台湾","广西","内蒙古","西藏","宁夏","新疆",
]

METHOD_PATTERNS = [
    (r"公开招标", "公开招标"), (r"竞争性磋商", "竞争性磋商"),
    (r"竞争性谈判", "竞争性谈判"), (r"单一来源", "单一来源"),
    (r"询价|询比", "询价"), (r"中标结果|中标公告", "中标公告"),
    (r"中标候选人", "中标候选人"), (r"更正公告|变更公告", "更正公告"),
    (r"资格预审", "资格预审"), (r"邀请招标", "邀请招标"),
    (r"谈判采购", "谈判采购"), (r"竞价", "竞价"),
    (r"比选", "比选"), (r"招标公告|采购公告", "公开招标"),
]


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def load_existing_ids():
    if not os.path.exists(DATA_FILE):
        return set()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {md5(b["sourceUrl"]) for b in data.get("bids", [])}
    except:
        return set()


def load_existing_bids():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("bids", [])
    except:
        return []


def save_bids(bids):
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for b in bids if b.get("date") == today_str)
    output = {
        "todayCount": today_count,
        "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "bids": bids,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))


def safe_get(url, session):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (404, 403, 429):
                return None
        except:
            if attempt < MAX_RETRIES:
                time.sleep(1)
    return None


def extract_industry(title):
    full_text = title
    for ind, kws in INDUSTRY_KEYWORDS.items():
        if any(kw in full_text for kw in kws):
            return ind
    return ""


def extract_region(title):
    for prov in PROVINCE_KEYWORDS:
        if prov in title:
            return prov
    return ""


def extract_method(title, cat_id):
    method_map = {"89": "更正公告", "90": "中标结果", "91": "中标候选人", "92": "资格预审"}
    if cat_id in method_map:
        return method_map[cat_id]
    for pat, name in METHOD_PATTERNS:
        if re.search(pat, title):
            return name
    return ""


def crawl_page(session, params):
    """爬取单页列表，返回 (items, total_pages, continue_flag)"""
    url = LIST_URL + "?" + urlencode(params)
    resp = safe_get(url, session)
    if resp is None:
        return [], 0, False

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table_text")
    if not table:
        return [], 0, False

    rows = table.find_all("tr")
    items = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        link = cells[0].find("a")
        if not link:
            continue
        href = link.get("href", "")
        uuid_match = re.search(r"urlOpen\('([a-f0-9\-]+)'\)", href)
        if not uuid_match:
            continue
        uuid_str = uuid_match.group(1)
        title = link.get("title") or link.get_text(strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        date_text = cells[4].get_text(strip=True)

        source_url = DETAIL_URL_TPL.format(uuid=uuid_str)
        items.append({
            "id": md5(source_url)[:12],
            "uuid": uuid_str,
            "title": title,
            "industry_list": cells[1].get_text(strip=True),
            "region_list": cells[2].get_text(strip=True),
            "date": date_text.strip(),
            "sourceUrl": source_url,
        })

    # 分页信息
    pagination = soup.find("div", class_="pagination")
    total_pages = 0
    if pagination:
        label = pagination.find("label")
        if label:
            try:
                total_pages = int(label.get_text(strip=True))
            except:
                pass

    return items, total_pages, True


def crawl_category(cat_id, start_date, end_date, existing_ids, max_pages=500):
    """爬取单个分类（并发版）"""
    cat_name = CATEGORIES.get(cat_id, cat_id)
    print(f"\n{'='*50}")
    print(f"分类: {cat_name} ({cat_id})")
    print(f"日期: {start_date} ~ {end_date}")
    print(f"{'='*50}")

    session = requests.Session()
    new_bids = []
    skipped = 0
    pages_scanned = 0
    pages_done = False
    batch_id = 0

    # 先爬第1页获取总页数
    params = {
        "categoryId": cat_id,
        "publishTimeStart": start_date,
        "publishTimeEnd": end_date,
        "page": "1",
    }
    items, total_pages, _ = crawl_page(session, params)
    pages_scanned = 1

    if not items:
        print(f"  → 无数据，跳过")
        return []

    total_pages = min(total_pages, max_pages) if total_pages > 0 else max_pages
    print(f"  共 {total_pages} 页，每页 ~{len(items)} 条")

    # 处理第1页
    for it in items:
        url_md5 = md5(it["sourceUrl"])
        if url_md5 not in existing_ids:
            existing_ids.add(url_md5)
            new_bids.append(make_bid(it, cat_id))

    # 并发爬取剩余页
    def fetch_page(page_num):
        nonlocal batch_id
        p = {"categoryId": cat_id, "publishTimeStart": start_date,
             "publishTimeEnd": end_date, "page": str(page_num)}
        sess = requests.Session()
        items, _, _ = crawl_page(sess, p)
        time.sleep(PAGE_DELAY)
        return items

    page_nums = list(range(2, total_pages + 1))
    with ThreadPoolExecutor(max_workers=CONCURRENT) as ex:
        futures = {ex.submit(fetch_page, pn): pn for pn in page_nums}
        for fut in as_completed(futures):
            pn = futures[fut]
            pages_scanned += 1
            try:
                items = fut.result()
            except:
                items = []
            if not items:
                continue
            for it in items:
                url_md5 = md5(it["sourceUrl"])
                if url_md5 in existing_ids:
                    skipped += 1
                    continue
                existing_ids.add(url_md5)
                new_bids.append(make_bid(it, cat_id))

            if pages_scanned % 100 == 0:
                print(f"  → 第{pn}页 | 已扫描{pages_scanned}/{total_pages} | 新增{len(new_bids)} | 跳过{skipped}", flush=True)

    # 增量保存
    if new_bids:
        existing = load_existing_bids()
        final = existing + new_bids
        final.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_bids(final)
        print(f"  💾 已保存（共{len(final)}条）", flush=True)

    print(f"\n  📊 {cat_name}完成: 新增{len(new_bids)}, 跳过{skipped}, 扫描{pages_scanned}页")
    return new_bids


def make_bid(it, cat_id):
    title = it["title"]
    return {
        "id": it["id"],
        "title": title,
        "source": "招标投标公共服务平台",
        "industry": it.get("industry_list", "") or extract_industry(title),
        "region": it.get("region_list", "").strip("【】").strip() or extract_region(title),
        "method": extract_method(title, cat_id),
        "budget": "",
        "date": it["date"],
        "deadline": "",
        "buyer": "",
        "code": "",
        "sourceUrl": it["sourceUrl"],
        "content": f"<div class=\"pdf-pending\"><pre>内容待提取 (UUID: {it['uuid']})</pre></div>",
    }


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"🚀 cebpub 批量高速爬虫启动")
    print(f"   日期范围: {start_date} ~ {today}")
    print(f"   分类: {', '.join(CATEGORIES.values())}")
    print(f"   模式: 元数据快速爬取（跳过PDF）")

    existing_ids = load_existing_ids()
    existing_bids = load_existing_bids()
    print(f"   已有标讯: {len(existing_bids)} 条")

    all_new = []

    # 按分类逐个爬取，每个分类最多爬尽可用的页数
    for cat_id in CATEGORIES:
        # 89更正/90中标/91候选人: 500页, 92资格预审: 200页
        max_p = 200 if cat_id == "92" else 500
        new_bids = crawl_category(cat_id, start_date, today, existing_ids, max_pages=max_p)
        all_new.extend(new_bids)

    # 合并保存
    if all_new:
        final = existing_bids + all_new
        final.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_bids(final)
        print(f"\n✅ 全部完成: 新增 {len(all_new)} 条, 总计 {len(final)} 条")
        print(f"   更新 todayCount={final[0].get('date','') == today} 条今日数据")
    else:
        print(f"\n✅ 全部完成: 无新增数据")

    return len(all_new)


if __name__ == "__main__":
    main()
