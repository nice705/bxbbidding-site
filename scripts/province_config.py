#!/usr/bin/env python3
"""标讯宝 · 31省全覆盖配置

数据来源类型：
  CCGP  → 各省级政府采购网 (ccgp-xxx.gov.cn)
  GGZY  → 各省级公共资源交易中心 (ggzy.xxx.gov.cn / xxx.gov.cn)
  CEB   → 各省级招投标公共服务平台 (ctbpsp.com / provincial)
  DEPT  → 省级厅局级单位（教育局/体育局/卫健委/住建厅等）
  NTL   → 国家级平台

省份代码（拼音缩写，用于URL构造）：
  bj=北京, tj=天津, sh=上海, cq=重庆
  he=河北, sx=山西, nm=内蒙古, ln=辽宁, jl=吉林, hl=黑龙江
  js=江苏, zj=浙江, ah=安徽, fj=福建, jx=江西, sd=山东, ha=河南
  hb=湖北, hn=湖南, gd=广东, gx=广西, hi=海南
  sc=四川, gz=贵州, yn=云南, xz=西藏, sn=陕西, gs=甘肃, qh=青海
  nx=宁夏, xj=新疆
"""

PROVINCES = {
    # ── 4个直辖市 ──────────────────────────────────────────
    "北京": {"code": "bj", "pinyin": "beijing", "region": "华北", "ccgp_url": "http://www.ccgp-beijing.gov.cn/"},
    "天津": {"code": "tj", "pinyin": "tianjin", "region": "华北", "ccgp_url": "http://www.ccgp-tianjin.gov.cn/"},
    "上海": {"code": "sh", "pinyin": "shanghai", "region": "华东", "ccgp_url": "http://www.ccgp-shanghai.gov.cn/"},
    "重庆": {"code": "cq", "pinyin": "chongqing", "region": "西南", "ccgp_url": "http://www.ccgp-chongqing.gov.cn/"},

    # ── 22个省 ────────────────────────────────────────────
    "河北": {"code": "he", "pinyin": "hebei", "region": "华北", "ccgp_url": "http://www.ccgp-hebei.gov.cn/"},
    "山西": {"code": "sx", "pinyin": "shanxi", "region": "华北", "ccgp_url": "http://www.ccgp-shanxi.gov.cn/"},
    "辽宁": {"code": "ln", "pinyin": "liaoning", "region": "东北", "ccgp_url": "http://www.ccgp-liaoning.gov.cn/"},
    "吉林": {"code": "jl", "pinyin": "jilin", "region": "东北", "ccgp_url": "http://www.ccgp-jilin.gov.cn/"},
    "黑龙江": {"code": "hl", "pinyin": "heilongjiang", "region": "东北", "ccgp_url": "http://www.ccgp-hlj.gov.cn/"},

    "江苏": {"code": "js", "pinyin": "jiangsu", "region": "华东", "ccgp_url": "http://www.ccgp-jiangsu.gov.cn/"},
    "浙江": {"code": "zj", "pinyin": "zhejiang", "region": "华东", "ccgp_url": "http://www.ccgp-zhejiang.gov.cn/"},
    "安徽": {"code": "ah", "pinyin": "anhui", "region": "华东", "ccgp_url": "http://www.ccgp-anhui.gov.cn/"},
    "福建": {"code": "fj", "pinyin": "fujian", "region": "华东", "ccgp_url": "http://www.ccgp-fujian.gov.cn/"},
    "江西": {"code": "jx", "pinyin": "jiangxi", "region": "华东", "ccgp_url": "http://www.ccgp-jiangxi.gov.cn/"},
    "山东": {"code": "sd", "pinyin": "shandong", "region": "华东", "ccgp_url": "http://www.ccgp-shandong.gov.cn/"},

    "河南": {"code": "ha", "pinyin": "henan", "region": "华中", "ccgp_url": "http://www.ccgp-henan.gov.cn/"},
    "湖北": {"code": "hb", "pinyin": "hubei", "region": "华中", "ccgp_url": "http://www.ccgp-hubei.gov.cn/"},
    "湖南": {"code": "hn", "pinyin": "hunan", "region": "华中", "ccgp_url": "http://www.ccgp-hunan.gov.cn/"},

    "广东": {"code": "gd", "pinyin": "guangdong", "region": "华南", "ccgp_url": "http://www.ccgp-guangdong.gov.cn/"},
    "广西": {"code": "gx", "pinyin": "guangxi", "region": "华南", "ccgp_url": "http://www.ccgp-guangxi.gov.cn/"},
    "海南": {"code": "hi", "pinyin": "hainan", "region": "华南", "ccgp_url": "http://www.ccgp-hainan.gov.cn/"},

    "四川": {"code": "sc", "pinyin": "sichuan", "region": "西南", "ccgp_url": "http://www.ccgp-sichuan.gov.cn/"},
    "贵州": {"code": "gz", "pinyin": "guizhou", "region": "西南", "ccgp_url": "http://www.ccgp-guizhou.gov.cn/"},
    "云南": {"code": "yn", "pinyin": "yunnan", "region": "西南", "ccgp_url": "http://www.ccgp-yunnan.gov.cn/"},
    "西藏": {"code": "xz", "pinyin": "xizang", "region": "西南", "ccgp_url": "http://www.ccgp-xizang.gov.cn/"},

    "陕西": {"code": "sn", "pinyin": "shaanxi", "region": "西北", "ccgp_url": "http://www.ccgp-shaanxi.gov.cn/"},
    "甘肃": {"code": "gs", "pinyin": "gansu", "region": "西北", "ccgp_url": "http://www.ccgp-gansu.gov.cn/"},
    "青海": {"code": "qh", "pinyin": "qinghai", "region": "西北", "ccgp_url": "http://www.ccgp-qinghai.gov.cn/"},

    "宁夏": {"code": "nx", "pinyin": "ningxia", "region": "西北", "ccgp_url": "http://www.ccgp-ningxia.gov.cn/"},
    "新疆": {"code": "xj", "pinyin": "xinjiang", "region": "西北", "ccgp_url": "http://www.ccgp-xinjiang.gov.cn/"},

    # ── 自治区（部分已在上方）──
    "内蒙古": {"code": "nm", "pinyin": "neimenggu", "region": "华北", "ccgp_url": "http://www.ccgp-neimenggu.gov.cn/"},
}

# ── 国家级平台 ──────────────────────────────────────────
NATIONAL_PLATFORMS = [
    {"name": "中国政府采购网(中央)", "url": "http://www.ccgp.gov.cn/", "type": "CCGP"},
    {"name": "中国政府采购网(搜索)", "url": "http://search.ccgp.gov.cn/", "type": "CCGP"},
    {"name": "全国公共资源交易平台", "url": "http://www.ggzy.gov.cn/", "type": "GGZY"},
    {"name": "中国招标投标公共服务平台", "url": "http://www.cebpubservice.com/", "type": "CEB"},
    {"name": "中国招标网", "url": "https://www.chinabidding.com.cn/", "type": "OTHER"},
    {"name": "bidcenter招标中心", "url": "https://www.bidcenter.com.cn/", "type": "OTHER"},
    {"name": "中国国际招标网", "url": "https://www.chinabidding.mofcom.gov.cn/", "type": "OTHER"},
]

# ── 各省厅局级单位（实测可达URL，阿里云验证）──
DEPT_URLS = {
    # 直辖市
    "北京": ["http://jw.beijing.gov.cn/", "http://wjw.beijing.gov.cn/", "http://tyj.beijing.gov.cn/"],
    "天津": ["https://jy.tj.gov.cn/",],
    "上海": ["https://edu.sh.gov.cn/", "https://wsjkw.sh.gov.cn/", "https://tyj.sh.gov.cn/"],
    "重庆": ["http://jw.cq.gov.cn/", "http://wsjkw.cq.gov.cn/", "http://tyj.cq.gov.cn/"],
    # 华北
    "河北": ["http://jyt.hebei.gov.cn/",],
    "山西": ["http://jyt.shanxi.gov.cn/", "http://tyj.shanxi.gov.cn/"],
    "内蒙古": ["http://jyt.nmg.gov.cn/",],
    # 东北
    "辽宁": ["https://jyt.ln.gov.cn/", "https://wsjk.ln.gov.cn/", "http://tyj.ln.gov.cn/"],
    "吉林": ["http://jyt.jl.gov.cn/", "http://wsjkw.jl.gov.cn/"],
    "黑龙江": ["http://jyt.hlj.gov.cn/",],
    # 华东
    "江苏": ["http://jyt.jiangsu.gov.cn/", "http://wjw.jiangsu.gov.cn/"],
    "浙江": ["http://jyt.zj.gov.cn/", "https://wsjkw.zj.gov.cn/", "https://tyj.zj.gov.cn/"],
    "安徽": ["https://jyt.ah.gov.cn/",],
    "福建": ["http://jyt.fujian.gov.cn/", "http://tyj.fujian.gov.cn/"],
    "江西": ["http://jyt.jiangxi.gov.cn/", "http://tyj.jiangxi.gov.cn/"],
    "山东": ["http://wsjkw.shandong.gov.cn/",],
    # 华中
    "河南": ["http://jyt.henan.gov.cn/", "http://wsjkw.henan.gov.cn/", "http://tyj.henan.gov.cn/"],
    "湖北": ["https://wjw.hubei.gov.cn/",],
    "湖南": ["http://jyt.hunan.gov.cn/", "http://wjw.hunan.gov.cn/"],
    # 华南
    "广东": ["https://edu.gd.gov.cn/", "https://wsjkw.gd.gov.cn/", "http://tyj.gd.gov.cn/"],
    "广西": ["http://jyt.gxzf.gov.cn/", "http://wsjkw.gxzf.gov.cn/"],
    "海南": ["http://edu.hainan.gov.cn/"],
    # 西南
    "四川": ["https://edu.sc.gov.cn/", "https://wsjkw.sc.gov.cn/"],
    "贵州": ["http://jyt.guizhou.gov.cn/", "http://tyj.guizhou.gov.cn/"],
    "云南": ["https://jyt.yn.gov.cn/",],
    "西藏": ["http://edu.xizang.gov.cn/",],
    # 西北
    "陕西": ["http://jyt.shaanxi.gov.cn/", "http://tyj.shaanxi.gov.cn/"],
    "甘肃": [],
    "青海": ["http://jyt.qinghai.gov.cn/", "http://wsjkw.qinghai.gov.cn/", "http://tyj.qinghai.gov.cn/"],
    "宁夏": ["http://jyt.nx.gov.cn/", "https://wsjkw.nx.gov.cn/", "http://sport.nx.gov.cn/"],
    "新疆": ["http://jyt.xinjiang.gov.cn/", "http://tyj.xinjiang.gov.cn/"],
}

# ── 招标关键词（全行业全覆盖）──
# 用于识别政府网站上的采购/招标/中标/意向等相关内容
KEYWORDS = [
    "招标", "公告", "采购", "中标", "磋商", "谈判", "询价", "竞价",
    "公示", "征集", "邀标", "比选", "投标", "成交", "废标",
    "合同", "单一来源", "更正", "终止", "验收", "结果", "意向",
    "竞争性", "公开招标", "资格预审", "框架协议",
    "征求意见", "意见征集",  # 采购意向征集也是重要的
    "通告", "招标公告", "采购公告", "中标公告", "成交公告",
    "竞争性磋商", "竞争性谈判",
]

# ── 排除关键词（仅排除明显非招标内容）──
EXCLUDE_KEYWORDS = [
    "问卷调查",
    "网站建设",
    "专家库",
    "注册流程",
    "重置密码",
    "操作指南",
    "系统登录",
    "技术咨询",
    "常见问题",
    "办事指南",
    "服务热线",
    "关于对2026年",  # 目录/标准
    "关于对2025年",
    "2026年政府集中采购目录",
    "2025年政府集中采购目录",
    "中小企业预留份额",
    "服务企业高质量发展",
]

# ── 各省公共资源交易中心（补充，非CCGP覆盖的）──
GGZY_EXTRA = {
    "广东": "https://ygp.gdzwfw.gov.cn/",
    "浙江": "https://zjpubservice.zjzwfw.gov.cn/",
    "江苏": "http://jsggzy.jszwfw.gov.cn/",
    "北京": "https://www.bjggzyfw.gov.cn/",
    "上海": "https://www.shggzy.com/",
    "深圳": "https://www.szggzy.com/",
    "河北": "http://www.hbggzyjy.com/",
    "内蒙古": "https://ggzyjy.nmg.gov.cn/",
    "广西": "http://ggzy.jgswj.gxzf.gov.cn/gxggzy/",
    "甘肃": "https://ggzyjy.gansu.gov.cn/",
    "宁夏": "https://ggzyjy.fzggw.nx.gov.cn/",
}


def get_province(name):
    """按中文名取省份配置"""
    return PROVINCES.get(name)

def all_provinces():
    """返回所有省份列表"""
    return list(PROVINCES.keys())

def ccgp_urls():
    """返回所有省CCGP URL"""
    return [(name, info["ccgp_url"]) for name, info in PROVINCES.items()]

def dept_urls(province=None):
    """返回厅局URL"""
    if province:
        return [(province, url) for url in DEPT_URLS.get(province, [])]
    result = []
    for prov, urls in DEPT_URLS.items():
        for url in urls:
            result.append((prov, url))
    return result
