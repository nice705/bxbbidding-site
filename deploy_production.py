#!/usr/bin/env python3
"""
标讯宝 · 全自动部署（v4 - wrangler 版）

工作流：
  1. 准备数据（enriched 优先，降级旧版）
  2. 生成 bids.json.gz（压缩版，供 Pages Function 使用）
  3. wrangler pages deploy 部署到生产

依赖：服务器 npx 可用（已修复）
"""
import json, os, sys, shutil, gzip, subprocess, time
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path("/home/hermes/projects/bidding-site")
CRAWLER_DATA_DIR = Path("/home/hermes/bid-crawler/data")


def log(msg):
    print(f"  {msg}")


# ═══════════ 步骤 1: 准备数据 ═══════════
def prepare_data() -> bool:
    # 生成 sitemap（5秒超时，失败不影响部署）
    import subprocess
    subprocess.run(["timeout","5","python3","/home/hermes/projects/bidding-site/generate_sitemap_fast.py"], capture_output=True, timeout=10)
    """准备数据文件：AI enriched 优先，降级旧版"""
    data_dir = PROJECT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    any_data = False

    # 首页数据：enriched-homepage.json
    src_home = CRAWLER_DATA_DIR / "enriched-homepage.json"
    dst_home = data_dir / "bids-homepage.json"
    if src_home.exists():
        shutil.copy2(src_home, dst_home)
        bids = json.loads(dst_home.read_text()).get("bids", [])
        bidding = sum(1 for b in bids if b.get("is_bidding", True))
        log(f"✅ 首页 (AI): {len(bids)} 条, 招标 {bidding} 条")
        any_data = True
    else:
        src_legacy = CRAWLER_DATA_DIR / "bids-homepage.json"
        if src_legacy.exists():
            shutil.copy2(src_legacy, dst_home)
            bids = json.loads(dst_home.read_text()).get("bids", [])
            log(f"⚠️ 首页 (降级): {len(bids)} 条")
            any_data = True
        else:
            log("❌ 无首页数据")
            return False

    # 全量数据：enriched-bids.json
    src_full = CRAWLER_DATA_DIR / "enriched-bids.json"
    dst_full = data_dir / "bids.json"
    if src_full.exists():
        shutil.copy2(src_full, dst_full)
        data = json.loads(dst_full.read_text())
        bids = data.get("bids", [])
        bidding = sum(1 for b in bids if b.get("is_bidding", True))
        log(f"✅ 全量 (AI): {len(bids)} 总, {bidding} 招标")

        # 统计
        buyer = sum(1 for b in bids if b.get("buyer"))
        deadline = sum(1 for b in bids if b.get("deadline"))
        log(f"📊 采购单位: {buyer} | 截止时间: {deadline}")
    else:
        log("ℹ️ 无 enriched-bids.json（不影响首页部署）")



    # 生成 bids-detail.json（详情页快速加载用，前2000条）
    KEYS = ["id","title","method","region","buyer","budget","date","deadline","products","source","hasAttachment","attachments","content"]
    dst_detail = data_dir / "bids-detail.json"
    detail_bids = []
    for b in bids[:2000]:
        slim = {k: b.get(k) for k in KEYS}
        if slim.get("content") and len(slim["content"]) > 2000:
            slim["content"] = slim["content"][:2000] + "..."
        detail_bids.append(slim)
    (data_dir / "bids-detail.json").write_text(json.dumps({"bids": detail_bids}, ensure_ascii=False))
    log(f"✅ bids-detail.json: {len(detail_bids)} 条")
    return any_data


# ═══════════ 步骤 2: 生成 bids.json.gz ═══════════
def create_gzip():
    """将 bids.json 压缩为 bids.json.gz（Pages Function 依赖此文件）"""
    src = PROJECT_DIR / "data" / "bids.json"
    dst = PROJECT_DIR / "data" / "bids.json.gz"
    if not src.exists():
        log("⚠️ bids.json 不存在，跳过生成 gz")
        return False
    try:
        with open(src, "rb") as fin, gzip.open(dst, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        src_size = src.stat().st_size
        dst_size = dst.stat().st_size
        log(f"✅ bids.json.gz: {dst_size/1024/1024:.1f}MB (压缩 {dst_size/src_size*100:.0f}%)")
        return True
    except Exception as e:
        log(f"❌ 压缩失败: {e}")
        return False


# ═══════════ 步骤 3: wrangler 部署 ═══════════
    """复制附件到 Pages 部署目录"""
    src = "/home/hermes/bid-crawler/attachments"
    dst = os.path.join(str(PROJECT_DIR), "attachments")
    if not os.path.exists(src):
        log("⚠️ attachments 源目录不存在")
        return
    os.makedirs(dst, exist_ok=True)
    count = 0
    for fname in os.listdir(src):
        s = os.path.join(src, fname)
        if os.path.isfile(s):
            d = os.path.join(dst, fname)
            if not os.path.exists(d):
                shutil.copy2(s, d)
                count += 1
    log(f"✅ 附件复制: {count} 个 (已存于 {dst})")

def deploy_with_wrangler():
    """使用 wrangler CLI 部署到生产（main 分支）"""
    token_paths = ["/root/.cf_token", "/root/.cf_token_qgbxb"]
    token = None
    for p in token_paths:
        fp = Path(p)
        if fp.exists():
            token = fp.read_text().strip()
            break

    if not token:
        log("❌ CF token 未找到")
        return False

    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = "b64fb5724136bb8cf4542e87a31f5498"

    cmd = [
        "npx", "wrangler", "pages", "deploy",
        str(PROJECT_DIR),
        "--project-name", "bxbbidding-site-final-v3",
    ]

    log("📤 wrangler 部署中...")
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, env=env
        )
        elapsed = time.time() - t0
        output = r.stdout + r.stderr

        if "✨ Deployment complete" in output or "✨ Success" in output:
            log(f"✅ wrangler 部署成功 ({elapsed:.1f}s)")
            for line in output.splitlines():
                if "https://" in line or "Deployment complete" in line:
                    log(f"   {line.strip()}")
            return True
        else:
            log(f"❌ wrangler 失败 ({elapsed:.1f}s)")
            for line in output.splitlines():
                if "ERROR" in line or "error" in line.lower():
                    log(f"   {line.strip()}")
            return False
    except subprocess.TimeoutExpired:
        log("❌ wrangler 超时 (>300s)")
        return False
    except Exception as e:
        log(f"❌ wrangler 异常: {e}")
        return False


# ═══════════ 验证 ═══════════
def verify():
    """验证生产环境"""
    import urllib.request
    log("🔍 验证部署...")
    try:
        r = urllib.request.urlopen(urllib.request.Request("https://qgbxb.com/data/bids-homepage.json", headers={"User-Agent": "Mozilla/5.0 Chrome/125"}), timeout=15)
        if r.status == 200:
            data = json.loads(r.read())
            bids = data.get("bids", [])
            log(f"✅ qgbxb.com: {len(bids)} 条, 正常")
            return True
        else:
            log(f"⚠️ qgbxb.com: HTTP {r.status}")
            return False
    except Exception as e:
        log(f"⚠️ 验证超时: {e}")
        return False


# ═══════════ 主流程 ═══════════

# Step 2.5: Clean up large files (>20MB) to avoid Cloudflare Pages 25MB limit
def cleanup_large_files():
    large_paths = [
        PROJECT_DIR / 'data' / 'bids.json',
        PROJECT_DIR / 'data' / 'bids-full.json',
    ]
    for fp in large_paths:
        if fp.exists() and fp.stat().st_size > 20 * 1024 * 1024:
            mb = fp.stat().st_size / 1024 / 1024
            fp.unlink()
            log(f'Removed {fp.name} ({mb:.0f}MB) - exceeded Pages 25MB limit')
    return True

def main():
    print("=" * 55)
    print(f"  标讯宝 · 全自动部署 (v4)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # 步骤 1: 准备数据
    if not prepare_data():
        log("❌ 数据准备失败")
        return 1

    # 步骤 2: 构建客户历史数据
    log("📊 构建客户历史数据...")
    subprocess.run([sys.executable, "scripts/build_customer_history.py"],
                   cwd=str(CRAWLER_DATA_DIR.parent),
                   timeout=600,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 转换格式
    try:
        import json as _j
        hist_f = Path("/home/hermes/projects/bidding-site/data/customer_history.json")
        if hist_f.exists():
            hd = _j.loads(hist_f.read_bytes())
            cl = []
            for n, d in hd.items():
                if not isinstance(d, dict): continue
                inf = d.get("info",{})
                hst = d.get("history",[])
                cl.append({
                    "buyer": n,
                    "bidder": inf.get("bidder",""),
                    "brands": inf.get("brands",[]),
                    "amount": inf.get("amount",0),
                    "source": hst[0].get("source",inf.get("source","")) if hst else "",
                    "region": hst[0].get("region",inf.get("region","")) if hst else "",
                    "date": hst[0].get("date",inf.get("date","")) if hst else "",
                    "bid_id": hst[0].get("bid_id",inf.get("bid_id",0)) if hst else 0,
                    "title": hst[0].get("title",inf.get("title","")) if hst else "",
                    "total_bids": len(hst),
                    "total_amount": sum(h.get("amount",0) for h in hst if h.get("amount")),
                })
            Path("/home/hermes/projects/bidding-site/data/customers.json").write_text(
                _j.dumps({"stats":{"total_customers":len(cl)},"customers":cl}, ensure_ascii=False))
            log(f"✅ customers.json: {len(cl)} 客户")
    except Exception as e:
        log(f"⚠️ 客户数据转换失败: {e}")

    # 步骤 3: 注入附件路径到 bids.json
    log("📎 注入附件路径...")
    subprocess.run([sys.executable, "scripts/inject_attachments.py"],
                   cwd=str(CRAWLER_DATA_DIR.parent))

    # 注入后重新同步 enriched-bids.json → bids.json（注入写入了 CRAWLER 目录）
    src_enriched = CRAWLER_DATA_DIR / "enriched-bids.json"
    dst_enriched = PROJECT_DIR / "data" / "bids.json"
    if src_enriched.exists() and dst_enriched.exists():
        shutil.copy2(src_enriched, dst_enriched)
        log("✅ 重新同步 enriched → bids.json (含附件信息)")

    # 步骤 3: 重新生成 gz（含附件信息）
    # 步骤 4: 生成 per-bid 独立文件（详情页快速加载）
    log("📦 生成 per-bid 独立文件...")
    try:
        import json, gzip
        detail_path = PROJECT_DIR / "data" / "bids-detail.json"
        bid_dir = PROJECT_DIR / "bid"
        bid_dir.mkdir(parents=True, exist_ok=True)
        with open(detail_path) as f:
            detail = json.load(f)
        detail_bids = detail["bids"] if isinstance(detail, dict) else detail
        count = 0
        for bid in detail_bids:
            bid_id = bid.get("id")
            if bid_id:
                # 确保 attachments 是列表（避免 JSON 字符串）
                att_raw = bid.get("attachments", [])
                if isinstance(att_raw, str):
                    try:
                        bid["attachments"] = json.loads(att_raw)
                    except (json.JSONDecodeError, TypeError):
                        bid["attachments"] = []
                fp = bid_dir / (str(bid_id) + ".json")
                if not fp.exists():
                    with open(fp, "w", encoding="utf-8") as f:
                        json.dump(bid, f, ensure_ascii=False)
                    count += 1
        if count > 0:
            log(f"✅ 生成 {count} 个 per-bid 文件")
    except Exception as e:
        log(f"⚠️ per-bid 生成失败: {e}")

    create_gzip()

    # 步骤 3.5: 复制附件到部署目录

    # 步骤 4: 清理大文件
    cleanup_large_files()

    # 步骤 5: wrangler 部署
    if not deploy_with_wrangler():
        log("❌ wrangler 部署失败")
        return 1

    # 验证
    verify()
    print("\n✅ 全部完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
