#!/usr/bin/env python3
"""Append big data analysis to existing Feishu doc."""

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
blocks.append(h1("九、补充：大数据板块深度分析"))
blocks.append(p("通过分析 jrbx.com wxclient 的 bigdata 板块 JS 代码，发现了完整的 B 端数据产品体系。这是今日标讯真正值钱的部分。"))
blocks.append(gap())

blocks.append(h2("9.1 完整功能矩阵"))
blocks.append(bp("招标预测 (tenderForecast)"))
blocks.append(b("业主单位基本信息展示"))
blocks.append(b("预计采购时间——预测未来什么时候发标"))
blocks.append(b("预测依据、预测原因（数据驱动）"))
blocks.append(b("潜在渠道商列表"))
blocks.append(b("加入公海池——CRM 线索管理"))
blocks.append(gap())

blocks.append(bp("经销商数据库 (dealer)"))
blocks.append(b("医疗器械代理商经销商名录（全国范围）"))
blocks.append(b("按产品分类 / 按产品名称 / 按企业 / 按科室 四维检索"))
blocks.append(b("经销商详情页：基本信息 + 联系人 + 电话"))
blocks.append(b("历史中标项目"))
blocks.append(b("合作品牌"))
blocks.append(b("经销产品、热招产品"))
blocks.append(b("备案信息（备案部门、备案时间）"))
blocks.append(gap())

blocks.append(bp("产品分析 (product/analysis)"))
blocks.append(b("分析产品市场规模——该产品全国招标数据统计"))
blocks.append(b("按科室分类分析"))
blocks.append(b("销售渠道分析"))
blocks.append(gap())

blocks.append(bp("企业分析 (company/analysis)"))
blocks.append(b("分析企业合作伙伴——该企业和哪些单位合作"))
blocks.append(b("竞争对手分析"))
blocks.append(gap())

blocks.append(bp("品牌分析 (brand)"))
blocks.append(b("按产品 / 按企业 / 按品牌 三维度分析"))
blocks.append(b("示例品牌：迈瑞（国内医疗设备龙头）"))
blocks.append(b("示例产品：医用口罩"))
blocks.append(gap())

blocks.append(bp("找渠道 (findChannels)"))
blocks.append(b("核心功能：帮厂商找代理商/经销商"))
blocks.append(b("按产品 / 按企业 搜索"))
blocks.append(b("热搜渠道——当前最热的渠道关键词"))
blocks.append(gap())

blocks.append(h2("9.2 今日标讯全貌功能层级"))
blocks.append(bp("第1层：标讯数据（基础层·免费）"))
blocks.append(b("全网聚合 3亿+ 标讯，每日更新 15万+"))
blocks.append(b("搜索 + 筛选 + 推荐"))
blocks.append(b("公告全文查看"))
blocks.append(gap())

blocks.append(bp("第2层：增值服务（会员层·付费）"))
blocks.append(b("公告联系人+电话（采购方/中标方）"))
blocks.append(b("附件下载"))
blocks.append(b("订阅推送 + 关键词提醒"))
blocks.append(gap())

blocks.append(bp("第3层：大数据分析（B端产品层·高价值）"))
blocks.append(b("招标预测——提前预知采购需求"))
blocks.append(b("经销商数据库——全国医疗器械代理商名录+联系方式"))
blocks.append(b("产品分析——市场规模、销售渠道"))
blocks.append(b("企业分析——合作伙伴、竞争对手"))
blocks.append(b("品牌分析——品牌市场分布"))
blocks.append(b("找渠道——精准匹配经销商"))
blocks.append(gap())

blocks.append(h2("9.3 变现逻辑总结"))
blocks.append(bp("数据免费 → 服务付费"))
blocks.append(b("免费：标讯搜索 + 全文查看（引流）"))
blocks.append(b("会员：联系人 + 附件 + 订阅（转化）"))
blocks.append(b("B端：大数据分析模块（高价值变现）"))
blocks.append(gap())
blocks.append(bp("用户画像"))
blocks.append(b("免费用户：销售代表、采购专员（草根用户）"))
blocks.append(b("VIP会员：医疗器械销售经理（付费意愿强）"))
blocks.append(b("B端客户：医疗设备厂商（企业版/年费）"))
blocks.append(gap())

blocks.append(h2("9.4 对我们的启示"))
blocks.append(b("标讯是入口，大数据分析才是真正的价值所在"))
blocks.append(b("从 '看标讯' 到 '找商机' 是产品升级的关键路径"))
blocks.append(b("经销商数据库 = jrbx 最核心的资产（全国代理商名录+联系方式）"))
blocks.append(b("我们可以先做标讯数据，数据量足够后逐步叠加分析功能"))
blocks.append(b("找渠道/招标预测这些功能依赖大量历史数据积累"))
blocks.append(gap())
blocks.append(p("— 大数据分析补充完成 —"))

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
