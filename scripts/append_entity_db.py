#!/usr/bin/env python3
"""Append entity database analysis to Feishu doc."""

import os, sys, time

APP_ID = os.environ.get('FEISHU_APP_ID', '').strip()
APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '').strip()
DOC_ID = "M2D6dLb76oKfsLxkdjOchQYMn9g"

sys.path.insert(0, '/home/hemers/.hermes/hermes-agent/.venv/lib/python3.11/site-packages')
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *
from lark_oapi.api.docx.v1.model.block import Block, Text as DocxText
from lark_oapi.api.docx.v1.model.create_document_block_children_request import CreateDocumentBlockChildrenRequestBody

client = (
    lark.Client.builder()
    .app_id(APP_ID).app_secret(APP_SECRET)
    .domain(lark.FEISHU_DOMAIN)
    .log_level(lark.LogLevel.WARNING)
    .build()
)

def el(text, bold=False):
    return TextElement.builder().text_run(
        TextRun.builder().content(text).text_element_style(
            TextElementStyle.builder().bold(bold).build()
        ).build()
    ).build()

def mk(bt, elems):
    type_key = {2:'text', 3:'heading1', 4:'heading2', 5:'heading3', 12:'bullet'}[bt]
    return getattr(Block.builder().block_type(bt), type_key)(
        DocxText.builder().elements(elems).build()
    ).build()

def h1(t): return mk(3, [el(t, True)])
def h2(t): return mk(4, [el(t)])
def h3(t): return mk(5, [el(t)])
def p(t): return mk(2, [el(t)])
def bp(t): return mk(2, [el(t, True)])
def b(t): return mk(12, [el(t)])
def gap(): return mk(2, [el("")])

blocks = []
blocks.append(gap())
blocks.append(h1("十一、补充：数据实体库（产品库/厂家库/医疗机构库/同行渠道）"))

blocks.append(p("JS 反编译发现了 4 个新的数据实体库模块，与之前分析的经销商库共同构成了完整的医疗器械行业数据库体系。"))
blocks.append(gap())

blocks.append(h2("11.1 完整大数据板块一览"))

blocks.append(bp("数据实体库层（查询检索）"))
blocks.append(b("医疗机构库 (medicalInstitutions)——查询所有医疗机构"))
blocks.append(b("厂家库 (factoryLibrary)——医疗器械生产厂家名录"))
blocks.append(b("产品库 (productLibrary)——医疗器械产品注册库"))
blocks.append(b("经销商库 (dealer)——医疗器械代理商经销商名录"))
blocks.append(b("同行渠道 (peerChannels)——同行/竞品渠道关系"))
blocks.append(gap())

blocks.append(bp("商业分析层（数据分析）"))
blocks.append(b("招标预测 (tenderForecast)——预知采购时间"))
blocks.append(b("产品分析 (product/analysis)——市场规模+科室分布"))
blocks.append(b("企业分析 (company/analysis)——合作伙伴+竞争对手"))
blocks.append(b("品牌分析 (brand)——品牌市场分布"))
blocks.append(b("找渠道 (findChannels)——精准匹配经销商"))
blocks.append(gap())

blocks.append(h2("11.2 各实体库详情"))

blocks.append(bp("医疗机构库 (medicalInstitutions)"))
blocks.append(b("查询所有医疗机构——覆盖全国医院/卫生院/诊所"))
blocks.append(b("支持关键词搜索"))
blocks.append(b("可从医疗机构维度进入其他分析模块"))
blocks.append(gap())

blocks.append(bp("产品库 (productLibrary)"))
blocks.append(b("医疗器械产品注册数据库"))
blocks.append(b("按产品名 / 按企业名 搜索"))
blocks.append(b("字段：上市时间、发布、批准文号、更新时间"))
blocks.append(b("关联：生产厂商 + 全国同类型产品生产厂家"))
blocks.append(gap())

blocks.append(bp("厂家库 (factoryLibrary)"))
blocks.append(b("医疗器械生产厂家名录"))
blocks.append(b("按产品 / 按企业 搜索"))
blocks.append(b("筛选维度：地区、类别"))
blocks.append(b("关联：经销商、医疗机构（关系图谱）"))
blocks.append(b("支持排序"))
blocks.append(gap())

blocks.append(bp("同行渠道 (peerChannels)"))
blocks.append(b("找同行渠道——了解同行/竞品的渠道分布"))
blocks.append(b("按厂家 / 按品牌 搜索"))
blocks.append(b("展示相关渠道关系"))
blocks.append(b("示例：迈瑞（深圳迈瑞生物医疗电子股份有限公司）"))
blocks.append(gap())

blocks.append(h2("11.3 数据实体库之间的关系"))
blocks.append(p("这5个实体库之间通过关系链接，形成了完整的医疗行业图谱："))
blocks.append(gap())
blocks.append(b("厂家 → 生产 → 产品"))
blocks.append(b("厂家 → 通过 → 经销商 → 销售"))
blocks.append(b("经销商 → 供货给 → 医疗机构"))
blocks.append(b("厂家 → 有 → 同行/竞品"))
blocks.append(b("厂家 + 产品 + 医疗机构 + 经销商 → 形成招投标关系"))
blocks.append(b("品牌 → 覆盖 → 多个产品"))
blocks.append(gap())

blocks.append(h2("11.4 数据实体库与标讯的联动"))
blocks.append(b("一条标讯涉及：采购方（医疗机构）+ 中标方（经销商/厂家）+ 产品"))
blocks.append(b("标讯详情页的 entity 抽取 → 自动关联到对应的实体库"))
blocks.append(b("实体库的查询结果 → 可反向查看该实体相关的所有标讯"))
blocks.append(gap())

blocks.append(h2("11.5 核心价值"))
blocks.append(b("数据实体库 = 结构化后的医疗器械行业知识图谱"))
blocks.append(b("这是比标讯本身更有商业价值的数据资产"))
blocks.append(b("厂家/经销商/医疗机构三者的关系链 = 精准销售线索"))
blocks.append(b("构建这样的数据库需要长期积累，一旦建成即形成壁垒"))

blocks.append(gap())
blocks.append(p("— 数据实体库分析补充完成 —"))

total = len(blocks)
print(f"Appending {total} blocks...")
for i in range(0, total, 20):
    batch = blocks[i:i+20]
    req_body = CreateDocumentBlockChildrenRequestBody.builder().children(batch).build()
    req = (CreateDocumentBlockChildrenRequest.builder()
        .document_id(DOC_ID).block_id(DOC_ID)
        .request_body(req_body).build())
    resp = client.docx.v1.document_block_children.create(req)
    if resp.code != 0:
        print(f"  ✗ Batch {i//20+1}: {resp.code} {resp.msg}")
    else:
        print(f"  ✓ Batch {i//20+1} ({len(batch)}块)")
    time.sleep(0.3)

print(f"\n✅ 完成！https://bytedance.feishu.cn/docx/{DOC_ID}")
