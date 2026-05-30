#!/usr/bin/env python3
"""
标讯宝 · 字段反填脚本

从已有公告 content 中提取 buyer、region、budget 等字段
并写入 bids.json。不重新爬取，纯本地处理。
"""

import json
import os
import re
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "bids.json")

PROVINCE_KEYWORDS = [
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东",
    "河南", "湖北", "湖南", "广东", "海南",
    "四川", "贵州", "云南", "陕西", "甘肃", "青海",
    "台湾", "广西", "内蒙古", "西藏", "宁夏", "新疆",
]


def extract_buyer(content: str, title: str) -> str:
    """从 content HTML 中提取采购单位"""
    if not content:
        return ""

    # 格式1: 采购人信息 → 名 称：xxx
    pattern1 = re.search(
        r'采购人信息[^<]*</p>\s*<p>[^<]*名\s*[称稱][：:]\s*([^<>\n]{2,60})',
        content
    )
    if pattern1:
        val = pattern1.group(1).strip()
        # 清理全角空格
        val = re.sub(r'\u3000+', '', val)
        if val and len(val) >= 2:
            return val

    # 格式2: 采购单位[：:] xxx
    pattern2 = re.search(
        r'采购(?:人|单位|方)[：:]\s*([^<>\n]{2,60})',
        content
    )
    if pattern2:
        val = pattern2.group(1).strip()
        val = re.sub(r'\u3000+', '', val)
        if val and len(val) >= 2:
            return val

    # 格式3: 招标人[：:] xxx
    pattern3 = re.search(
        r'招标(?:人|单位)[：:]\s*([^<>\n]{2,60})',
        content
    )
    if pattern3:
        val = pattern3.group(1).strip()
        val = re.sub(r'\u3000+', '', val)
        if val and len(val) >= 2:
            return val

    # 格式4: 业主[：:] xxx (少见)
    pattern4 = re.search(
        r'业主[：:]\s*([^<>\n]{2,40})',
        content
    )
    if pattern4:
        val = pattern4.group(1).strip()
        val = re.sub(r'\u3000+', '', val)
        if val and len(val) >= 2:
            return val

    # 格式5: 通用名 称：xxx（在表格里）
    pattern5 = re.search(
        r'名\s*[称稱][：:]\s*([^<>\n]{2,60})',
        content
    )
    if pattern5:
        val = pattern5.group(1).strip()
        val = re.sub(r'\u3000+', '', val)
        if val and len(val) >= 2:
            return val

    # 格式6: 采购人就是招标公告标题中的机构名称
    # 从 title 中提取：去除"项目"、"公开招标公告"等后缀，取开头部分
    # 这只作为最后手段
    return ""


def extract_budget(content: str, html: str = "") -> str:
    """从 content 中提取预算金额（万元，纯数字）"""
    text = content or html
    if not text:
        return ""

    patterns = [
        # 预算金额：(数字)万元（人民币）
        r'预算金额[：:]\s*([0-9,，.]+)\s*万\s*元',
        # 预算金额：(数字)元
        r'预算金额[：:]\s*([0-9,，.]+)\s*元',
        # 预算：(数字)万元
        r'预算[：:]\s*([0-9,，.]+)\s*万\s*元',
        # 预算金额：(数字)
        r'预算金额[：:]\s*([0-9,，.]+)\s*(?![^<>\n]*[^0-9,，.\s])',
        # 项目预算：(数字)万元
        r'项目预算[：:]\s*([0-9,，.]+)\s*万\s*元',
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            amt = m.group(1).replace(",", "").replace("，", "")
            try:
                float(amt)
                return amt
            except ValueError:
                continue
    return ""


def extract_region(content: str, title: str, buyer: str, source_url: str) -> str:
    """从 content + title + buyer 中提取省份"""
    # 1. 从 content 中的地址字段提取
    if content:
        # "地址：四川省南充市嘉陵区..."
        addr_match = re.search(
            r'地址[：:]\s*([^<>\n]{2,60})',
            content
        )
        if addr_match:
            addr = addr_match.group(1)
            for prov in PROVINCE_KEYWORDS:
                if prov in addr:
                    return prov

    # 2. 从 /dfgg/ 页面的 URL 路径提取
    if '/dfgg/' in source_url:
        # dfgg/xxx/ 中的 xxx 可能是省份缩写
        m = re.search(r'/dfgg/([^/]+)/', source_url)
        if m:
            path_seg = m.group(1)
            # 映射省份缩写 -> 全称
            region_map = {
                'bj': '北京', 'sh': '上海', 'tj': '天津', 'cq': '重庆',
                'he': '河北', 'sx': '山西', 'ln': '辽宁', 'jl': '吉林', 'hlj': '黑龙江',
                'js': '江苏', 'zj': '浙江', 'ah': '安徽', 'fj': '福建', 'jx': '江西', 'sd': '山东',
                'hn': '河南', 'hb': '湖北', 'hun': '湖南', 'gd': '广东', 'gx': '广西', 'hain': '海南',
                'sc': '四川', 'gz': '贵州', 'yn': '云南', 'xz': '西藏', 'sx': '陕西', 'gs': '甘肃', 'qh': '青海',
                'nx': '宁夏', 'xj': '新疆', 'nm': '内蒙古',
            }
            for abbr, prov in region_map.items():
                if abbr in path_seg.lower():
                    return prov

    # 3. 从 buyer 提取
    if buyer:
        for prov in PROVINCE_KEYWORDS:
            if prov in buyer:
                return prov

    # 4. 从 title 提取
    if title:
        for prov in PROVINCE_KEYWORDS:
            if prov in title:
                return prov

    return ""


def main():
    print(f"🚀 标讯字段反填脚本启动")
    print(f"   数据文件: {DATA_FILE}")

    if not os.path.exists(DATA_FILE):
        print(f"❌ 文件不存在: {DATA_FILE}")
        sys.exit(1)

    # 加载数据
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    bids = data.get("bids", [])
    print(f"   总标讯数: {len(bids)}")

    # 统计
    stats = {
        "buyer_empty_before": 0,
        "region_empty_before": 0,
        "budget_empty_before": 0,
        "buyer_filled": 0,
        "region_filled": 0,
        "budget_filled": 0,
    }

    for bid in bids:
        c = bid.get("content", "")
        t = bid.get("title", "")
        u = bid.get("sourceUrl", "")
        b = bid.get("buyer", "")
        r = bid.get("region", "")
        g = bid.get("budget", "")

        # 记录空值
        if not b.strip():
            stats["buyer_empty_before"] += 1
        if not r.strip():
            stats["region_empty_before"] += 1
        if not g.strip():
            stats["budget_empty_before"] += 1

        # 反填 buyer
        if not b.strip():
            buyer = extract_buyer(c, t)
            if buyer:
                bid["buyer"] = buyer
                stats["buyer_filled"] += 1

        # 反填 region
        if not r.strip():
            region = extract_region(c, t, bid.get("buyer", "") or b, u)
            if region:
                bid["region"] = region
                stats["region_filled"] += 1

        # 反填 budget
        if not g.strip():
            budget = extract_budget(c)
            if budget:
                bid["budget"] = budget
                stats["budget_filled"] += 1

    # 保存
    data["updatedAt"] = __import__("datetime").datetime.now().strftime(
        "%Y-%m-%dT%H:%M:%S+08:00"
    )
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    mb = os.path.getsize(DATA_FILE) / 1024 / 1024

    print(f"\n📊 结果统计:")
    print(f"   Buyer  之前空: {stats['buyer_empty_before']} → 反填: {stats['buyer_filled']}")
    print(f"   Region 之前空: {stats['region_empty_before']} → 反填: {stats['region_filled']}")
    print(f"   Budget 之前空: {stats['budget_empty_before']} → 反填: {stats['budget_filled']}")
    print(f"   文件大小: {mb:.1f} MB")
    print(f"\n✅ 完成!")


if __name__ == "__main__":
    main()
