#!/usr/bin/env python3
"""Append CRM analysis to Feishu doc."""

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
blocks.append(h1("十、补充：CRM 销售管理系统 (线索池->客户->项目->报表)"))
blocks.append(p("JS 反编译发现了完整的 CRM 系统，覆盖从线索获取到成交管理的全流程。"))
blocks.append(gap())

blocks.append(h2("10.1 CRM 功能地图"))
blocks.append(bp("线索池 (cluePool) —— 未认领的销售线索"))
blocks.append(b("显示公海池（未被领取的线索）"))
blocks.append(b("新建线索"))
blocks.append(b("领取 / 继续领取"))
blocks.append(b("关键词 + 地区 + 时间区间 + 跟进状态 多维筛选"))
blocks.append(b("时间筛选：最近七天/最近半年/本周/本月"))
blocks.append(gap())

blocks.append(bp("线索详情 (cluePool/detail) —— 单条线索全貌"))
blocks.append(b("线索详情展示"))
blocks.append(b("跟进记录——按时间线记录跟进历史"))
blocks.append(b("客户动态——该客户最近的行为（查看标讯/联系人等）"))
blocks.append(b("团队成员——查看/添加/移除协作人"))
blocks.append(b("更换负责人"))
blocks.append(b("分配 / 删除"))
blocks.append(b("编辑"))
blocks.append(b("联系人"))
blocks.append(gap())

blocks.append(bp("客户管理 (customer) —— 已转化客户"))
blocks.append(b("我的客户——分配给自己的客户列表"))
blocks.append(b("客户联系人——联系人信息管理"))
blocks.append(b("新建客户 / 新建联系人"))
blocks.append(b("签到打卡——拜访打卡"))
blocks.append(b("附近客户——基于地理位置的附近客户"))
blocks.append(gap())

blocks.append(bp("项目管理 (project) —— 跟进中的商机"))
blocks.append(b("我的项目——项目列表"))
blocks.append(b("新建项目"))
blocks.append(b("推进记录——项目进展追踪"))
blocks.append(b("销售阶段——项目处于哪个阶段"))
blocks.append(b("预计成交日期"))
blocks.append(b("项目授权——授权记录"))
blocks.append(b("重复项目——去重检测"))
blocks.append(b("申诉记录"))
blocks.append(gap())

blocks.append(bp("统计分析 (stats/report) —— 销售团队看板"))
blocks.append(b("数据概览：公海池线索数、已领取线索数、新增线索数、新增客户数、新增项目数、新增跟进数"))
blocks.append(b("销售简报：跟进总数、跟进客户数、跟进线索数、跟进项目数、拜访次数、拜访签到数、提交跟进记录名单"))
blocks.append(b("员工活跃度：活跃人数、沉默人数、活跃天数、最近使用时间"))
blocks.append(b("跟进排行：按部门/个人排行的跟进次数"))
blocks.append(b("跟进分布：按方式（上门拜访/电话沟通/微信沟通）+ 按时间（本周/昨天/本月）"))
blocks.append(b("沉默检测：超过一个月未跟进"))
blocks.append(gap())

blocks.append(h2("10.2 CRM 与标讯的联动"))
blocks.append(b("公告详情页的 '加入公海池' 按钮——标讯→线索 一键转化"))
blocks.append(b("线索详情可查看 '客户动态'——该客户看了哪些标讯"))
blocks.append(b("销售简报中的 '查看标讯数'、'查看医院数'、'查看渠道商数'"))
blocks.append(gap())

blocks.append(h2("10.3 核心价值"))
blocks.append(b("CRM 系统将 '标讯查看' 行为转化为了可追踪的销售流程"))
blocks.append(b("从 '看到标讯' (免费) → '领取线索' (会员) → '跟进转化' (团队协作)"))
blocks.append(b("统计分析让管理者能看到团队每个成员的工作量"))
blocks.append(b("这形成了完整闭环：数据(标讯) → 线索(联系人) → 客户(转化) → 项目(成交)"))

blocks.append(gap())
blocks.append(p("— CRM 分析补充完成 —"))

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
