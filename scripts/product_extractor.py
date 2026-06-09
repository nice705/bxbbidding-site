#!/usr/bin/env python3
"""
标讯宝 · 产品标签提取器 — 优化版

从标讯标题/内容中提取设备/产品名称作为标签。
仅匹配标题（快），无结果才看内容前500字符。

用法:
  python3 scripts/product_extractor.py
"""

import json, gzip, os, re, sys, time

# ── 医疗设备关键词库（按字数从长到短排序）──
KEYWORDS = sorted([
    "核磁共振成像系统","磁共振成像系统","数字减影血管造影","全自动生化分析仪",
    "彩色多普勒超声","体外冲击波碎石机","体外冲击波治疗仪","电磁式冲击波治疗仪",
    "压电式冲击波治疗仪","化学发光分析仪","主动脉球囊反搏","数字化X射线",
    "数字化摄影","移动式C形臂","口腔综合治疗台","中央监护系统",
    "神经肌肉刺激仪","冲击波碎石机","冲击波治疗仪","麻醉深度监测",
    "电子胃肠镜","电子结肠镜","十二指肠镜","电子内窥镜",
    "硬性内窥镜","纤维内窥镜","支气管镜","输尿管镜",
    "鼻咽喉镜","腹腔镜系统","宫腔镜系统","关节镜系统",
    "椎间孔镜","胆道镜","膀胱镜","肾镜","电切镜",
    "眼科OCT","眼底照相机","角膜地形图","生物测量仪",
    "超声乳化仪","玻璃体切割机",
    "血细胞分析仪","血气分析仪","凝血分析仪","免疫分析仪",
    "尿液分析仪","血液分析仪","电解质分析仪","流式细胞仪",
    "基因测序仪","核酸提取仪","全自动酶标仪",
    "高压灭菌器","低温灭菌器","清洗消毒机",
    "反渗透水处理","纯水机",
    "医院信息系统","电子病历","远程医疗","互联网医院",
    "手术麻醉系统","重症监护系统","合理用药系统",
    "叫号系统","分诊系统","排队系统",
    "LCD拼接屏","LED显示屏","UPS电源",
    "视频会议系统","教学设备","实验室设备","体育器材",
    "核磁共振","磁共振","骨密度仪",
    "CT","DR","CR","DSA","IABP","ECMO",
    "X光机","C型臂","钼靶","乳腺机",
    "胃肠机","透视机",
    "彩超","超声刀","超声骨刀","便携超声",
    "血管内超声","超声内镜",
    "监护仪","心电图机","动态心电图","除颤仪",
    "呼吸机","麻醉机","麻醉工作站",
    "输液泵","注射泵","输液工作站",
    "体外膜肺",
    "内窥镜","腹腔镜","宫腔镜","关节镜",
    "生化分析仪","酶标仪","洗板机","PCR仪",
    "高频电刀","氩气刀","双极电凝",
    "无影灯","手术床","手术灯","手术显微镜",
    "急救车","抢救车",
    "康复训练","理疗设备",
    "微波治疗仪","红外线治疗仪","紫外线治疗仪",
    "中频治疗仪","低频治疗仪","高频治疗仪",
    "激光治疗仪","红光治疗","蓝光治疗",
    "牵引床","蜡疗",
    "口腔CT","牙科手机","洁牙机","根管治疗仪","种植机",
    "裂隙灯","视野计","眼压计","验光仪",
    "病理切片","冰冻切片","脱水机","包埋机","染色机",
    "病床","护理床","多功能病床","转运床",
    "制氧机","吸引器","雾化器","血糖仪",
    "救护车","体检车","负压救护车",
    "信息化建设","网络安全",
    "服务器","存储设备","交换机","路由器","防火墙",
    "监控系统","门禁系统",
    "打印/复印纸","复印纸","打印机","复印机",
    "扫描仪","投影仪",
    "物业服务","物业管理","保洁","安保","食堂",
    "输液泵","抢救车",
    "冲击波a4","冲击波",
], key=len, reverse=True)

TITLE_PATTERN = re.compile(
    r'(?:(?:采购|招标|购置|更新|配备|供应|维保|维护)\s*[：:]\s*)?'  # 标题中的「采购：XX」
    r'([\u4e00-\u9fff]{2,10}(?:仪|机|器|系统|设备|装置|平台|软件))'
)

def extract_products(title, content=""):
    """快速提取产品标签（最多5个）"""
    t = title or ""
    c = (content or "")[:500]
    products = set()

    # 仅匹配标题（快路径）
    for kw in KEYWORDS:
        if len(products) >= 5:
            break
        if kw.lower() in t.lower():
            products.add(kw)

    # 标题正则补充（严格过滤）
    if len(products) < 5:
        for m in TITLE_PATTERN.findall(t):
            if len(products) >= 5:
                break
            m = m.strip()
            # 过滤掉非产品词
            if not m or len(m) < 2:
                continue
            if any(s in m for s in ["采购","招标","项目","公告","服务","维修","保养","改造","工程","管理","咨询","租赁","运输","印刷","保险","物业","保洁","绿化","养护","设计","监理","检测","认证","评估","审计","培训","会议","展览","广告","宣传","出版","翻译","调研","研究","开发","集成"]):
                continue
            # 必须包含产品特征后缀
            if not any(m.endswith(s) for s in ["仪","机","器","系统","设备","装置","平台","软件","镜","刀","车","床","灯","泵","柜","箱","包","剂","液","膜","网"]):
                continue
            if m not in products:
                products.add(m)

    # 无结果时看内容前500字
    if len(products) == 0 and c:
        for kw in KEYWORDS:
            if len(products) >= 3:
                break
            if kw.lower() in c.lower() and kw not in products:
                products.add(kw)

    return list(products)[:5]


if __name__ == '__main__':
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    gz_path = os.path.join(data_dir, "bids.json.gz")
    json_path = os.path.join(data_dir, "bids.json")

    path = gz_path if os.path.exists(gz_path) else json_path
    is_gz = path.endswith('.gz')

    t0 = time.time()
    open_fn = gzip.open if is_gz else open
    with open_fn(path, 'rt', encoding='utf-8') as f:
        data = json.load(f)

    bids = data.get('bids', [])
    total = len(bids)
    count = 0

    for i, bid in enumerate(bids):
        if 'products' not in bid or not bid['products']:
            products = extract_products(bid.get('title',''), bid.get('content',''))
            if products:
                bid['products'] = products
                count += 1
        if (i+1) % 1000 == 0:
            print(f"  {i+1}/{total}...", flush=True)

    elapsed = time.time() - t0
    print(f"处理 {total} 条 | 新增标签: {count} 条 | 耗时: {elapsed:.1f}s")

    with open_fn(path, 'wt', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    # 验证样本
    tagged = [b for b in bids if b.get('products')]
    print(f"有标签的标讯: {len(tagged)}/{total}")
    for b in tagged[:5]:
        print(f"  {b.get('title','')[:40]} → {b.get('products')}")

    print("✅ 产品提取完成")
