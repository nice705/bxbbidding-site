#!/usr/bin/env python3
"""
标讯宝 · cebpub 全历史全量高速爬虫

策略：
  1. 无分类限制，爬取 cebpub 全部公告
  2. 按月份分片，从 2018-01 到当前月
  3. 高并发异步请求
  4. 增量去重，只追加新数据

目标：1000万+ 条（全量历史覆盖）

用法：
  python3 scripts/spider_cebpub_historical.py                   # 全量扫描
  python3 scripts/spider_cebpub_historical.py --no-save         # 只预览不保存
  python3 scripts/spider_cebpub_historical.py --month 2026-05   # 只爬指定月
"""

import hashlib, json, os, re, sys, time, traceback
from datetime import datetime, timedelta
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed

import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

PDF_URL_TPL = "https://bulletin.cebpubservice.com/agency/api/agency-business/tenant-record/record-pdf/{}"

def _fetch_one_pdf(uuid):
    """Fetch PDF and extract text for one UUID"""
    try:
        url = PDF_URL_TPL.format(uuid)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        resp = urllib.request.urlopen(req, context=SSL_CTX, timeout=15)
        if resp.status != 200:
            return None
        pdf_bytes = resp.read()
        if len(pdf_bytes) < 200 or b"%PDF" not in pdf_bytes[:10]:
            return None
        if fitz is None:
            return None
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        text = text.strip()
        if len(text) < 30:
            return None
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace("

", "</p><p>").replace("
", "<br>")
        return "<p>" + text + "</p>"
    except Exception:
        return None

def batch_fetch_pdfs(bids):
    """Batch fetch PDF content for bids with pdf-pending"""
    to_fetch = []
    for i, b in enumerate(bids):
        c = b.get("content", "")
        if "pdf-pending" in c or "内容待提取" in c:
            m = re.search(r"UUID:\s*([a-f0-9]+)", c)
            if m:
                to_fetch.append((i, m.group(1)))
    if not to_fetch:
        return 0
    fixed = 0
    for batch_start in range(0, len(to_fetch), 20):
        batch = to_fetch[batch_start:batch_start+20]
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_fetch_one_pdf, uuid): idx for idx, uuid in batch}
            for fut in as_completed(futures):
                idx = futures[fut]
                html = fut.result()
                if html:
                    bids[idx]["content"] = html
                    fixed += 1
        time.sleep(0.1)
    return fixed

LIST_URL = "https://bulletin.cebpubservice.com/xxfbcmses/search/bulletin.html"
DETAIL_URL_TPL = "https://ctbpsp.com/#/bulletinDetail?uuid={uuid}"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DATA_FILE = os.path.join(DATA_DIR, "bids-cebpub.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://bulletin.cebpubservice.com/",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
PAGE_DELAY = 0.08
CONCURRENT = 20
MAX_PAGES_PER_MONTH = 9999

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
    (r"成交公告|成交结果", "成交公告"), (r"流标|废标|终止", "废标公告"),
    (r"征集公告", "征集公告"), (r"拍卖公告|拍卖", "拍卖公告"),
    (r"招商公告", "招商公告"), (r"异常公告", "异常公告"),
    (r"需求公示|采购需求", "需求公示"),
    (r"合同公告|合同公示", "合同公告"),
]


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def load_data():
    if not os.path.exists(DATA_FILE):
        return set(), []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        bids = data.get("bids", [])
        existing_ids = {md5(b["sourceUrl"]) for b in bids}
        return existing_ids, bids
    except:
        return set(), []


def save_data(bids):
    os.makedirs(DATA_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_count = sum(1 for b in bids if b.get("date", "")[:10] == today_str)
    output = {
        "todayCount": today_count,
        "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "bids": bids,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    return len(bids)


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


def extract_method(title):
    for pat, name in METHOD_PATTERNS:
        if re.search(pat, title):
            return name
    return ""


def crawl_page(session, params):
    url = LIST_URL + "?" + urlencode(params)
    resp = safe_get(url, session)
    if resp is None:
        return [], 0
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="table_text")
    if not table:
        return [], 0
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
    # 分页
    total_pages = 0
    pagination = soup.find("div", class_="pagination")
    if pagination:
        label = pagination.find("label")
        if label:
            try:
                total_pages = int(label.get_text(strip=True))
            except:
                pass
    return items, total_pages


def make_bid(it):
    title = it["title"]
    return {
        "id": it["id"],
        "title": title,
        "source": "招标投标公共服务平台",
        "industry": it.get("industry_list", "") or extract_industry(title),
        "region": it.get("region_list", "").strip("【】").strip() or extract_region(title),
        "method": extract_method(title),
        "budget": "",
        "date": it["date"],
        "deadline": "",
        "buyer": "",
        "code": "",
        "sourceUrl": it["sourceUrl"],
        "content": f'<div class="pdf-pending"><pre>内容待提取 (UUID: {it["uuid"]})</pre></div>',
    }


def crawl_month(start_date, end_date, existing_ids, no_save=False):
    """爬取指定月份，返回新增数量"""
    print(f"\n{'='*55}")
    print(f"📅 {start_date} ~ {end_date}")
    print(f"{'='*55}")
    
    session = requests.Session()
    new_bids = []
    skipped = 0
    pages_scanned = 0
    
    # 第1页获取总数
    params = {
        "publishTimeStart": start_date,
        "publishTimeEnd": end_date,
        "page": "1",
    }
    items, total_pages = crawl_page(session, params)
    pages_scanned = 1
    
    if not items:
        print(f"  → 本月无数据")
        return 0
    
    total_pages = min(total_pages, MAX_PAGES_PER_MONTH) if total_pages > 0 else 1
    print(f"  总页数: {total_pages} 页, 每页 ~{len(items)} 条")
    
    # 处理第1页
    for it in items:
        url_md5 = md5(it["sourceUrl"])
        if url_md5 not in existing_ids:
            existing_ids.add(url_md5)
            new_bids.append(make_bid(it))
    
    if total_pages <= 1:
        if new_bids:
            print(f"  → 新增 {len(new_bids)} 条")
        return len(new_bids)
    
    # 并发爬取剩余页
    def fetch_page(page_num):
        p = {"publishTimeStart": start_date, "publishTimeEnd": end_date, "page": str(page_num)}
        sess = requests.Session()
        page_items, _ = crawl_page(sess, p)
        time.sleep(PAGE_DELAY)
        return page_items
    
    page_nums = list(range(2, total_pages + 1))
    with ThreadPoolExecutor(max_workers=CONCURRENT) as ex:
        futures = {ex.submit(fetch_page, pn): pn for pn in page_nums}
        done_count = 0
        for fut in as_completed(futures):
            pn = futures[fut]
            pages_scanned += 1
            done_count += 1
            try:
                page_items = fut.result()
            except:
                page_items = []
            if not page_items:
                continue
            for it in page_items:
                url_md5 = md5(it["sourceUrl"])
                if url_md5 in existing_ids:
                    skipped += 1
                    continue
                existing_ids.add(url_md5)
                new_bids.append(make_bid(it))
            
            if done_count % 50 == 0:
                pct = int(done_count / len(page_nums) * 100)
                print(f"  → {done_count}/{len(page_nums)} 页 ({pct}%) | 新增 {len(new_bids)} | 跳过 {skipped}", flush=True)
    
    # 增量保存
    if new_bids:
        print(f"  📥 提取PDF内容...", flush=True)
        pdf_fixed = batch_fetch_pdfs(new_bids)
        print(f"  ✅ PDF提取完成: {pdf_fixed}/{len(new_bids)} 条有内容")
    if new_bids and not no_save:
        existing_ids_full, existing_bids = load_data()
        # 合并新老数据
        final_bids = existing_bids + new_bids
        final_bids.sort(key=lambda x: x.get("date", ""), reverse=True)
        save_data(final_bids)
        print(f"  💾 已保存: 共 {len(final_bids)} 条", flush=True)
    
    print(f"  📊 完成: 新增 {len(new_bids)}, 跳过 {skipped}, 扫描 {pages_scanned} 页")
    return len(new_bids)


def generate_month_ranges(start_year=2018, start_month=1):
    """生成月份范围 2018-01 ~ 当前月，从最近开始倒序"""
    now = datetime.now()
    ranges = []
    year, month = start_year, start_month
    while year < now.year or (year == now.year and month <= now.month):
        month_end = datetime(year, month, 1) + timedelta(days=32)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        start = f"{year:04d}-{month:02d}-01"
        end = month_end.strftime("%Y-%m-%d")
        ranges.append((start, end))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return list(reversed(ranges))  # 倒序：从最近开始


def main():
    no_save = "--no-save" in sys.argv
    
    # 如果指定了单月
    single_month = None
    for arg in sys.argv:
        if re.match(r"^\d{4}-\d{2}$", arg):
            single_month = arg
            break
    
    print(f"🚀 cebpub 全历史高速爬虫")
    print(f"   目标是覆盖 2018-01 ~ 至今 全部分类")
    print(f"   并发: {CONCURRENT} 线程 | 延迟: {PAGE_DELAY}s | 每页延迟: 页面/PAGE_DELAY")
    print(f"   数据文件: {DATA_FILE}")
    
    existing_ids, existing_bids = load_data()
    print(f"   已有标讯: {len(existing_bids)} 条\n")
    
    if single_month:
        ranges = [(single_month + "-01", single_month)]
    else:
        ranges = generate_month_ranges()
    
    total_new = 0
    total_skipped = 0
    start_time = time.time()
    
    for i, (s, e) in enumerate(ranges):
        if single_month:
            s = single_month + "-01"
            # 计算月末
            year, month = int(single_month[:4]), int(single_month[5:7])
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            e = f"{year:04d}-{month:02d}-{last_day:02d}"
        
        elapsed = time.time() - start_time
        print(f"\n[{i+1}/{len(ranges)}] 已耗时 {elapsed/60:.1f}min | 已新增 {total_new}")
        
        new_count = crawl_month(s, e, existing_ids, no_save)
        total_new += new_count
        
        # 每完成 3 个月输出一次进度摘要
        if (i + 1) % 3 == 0 or i == len(ranges) - 1:
            elapsed = time.time() - start_time
            rate = total_new / (elapsed / 3600) if elapsed > 0 else 0
            print(f"\n📊 进度: {i+1}/{len(ranges)} 个月")
            print(f"   耗时: {elapsed/60:.1f} min")
            print(f"   新增: {total_new:,} 条")
            print(f"   速率: {rate:.0f} 条/小时")
    
    # 最终保存
    if total_new > 0 and not no_save:
        _, existing_bids_final = load_data()
        final_count = len(existing_bids_final)
        print(f"\n{'='*55}")
        print(f"✅ 全量扫描完成!")
        print(f"   新增: {total_new:,} 条")
        print(f"   总计: {final_count:,} 条")
        print(f"   总耗时: {(time.time()-start_time)/60:.1f} min")
        
        # 按日期分布
        from collections import Counter
        date_dist = Counter(b.get("date","")[:7] for b in existing_bids_final)
        print(f"\n📈 月份分布 (前10):")
        for m, c in sorted(date_dist.items(), reverse=True)[:10]:
            print(f"   {m}: {c:,} 条")
    
    return total_new


if __name__ == "__main__":
    main()
