#!/usr/bin/env python3
"""标讯宝 · 部署准备工具

用法:
  # 1. 部署到 Cloudflare Pages 后，拿到你的域名（xxx.pages.dev）
  # 2. 运行此脚本替换所有占位 URL

  python3 scripts/deploy-prep.py your-domain.pages.dev

  或者绑定自定义域名后：
  python3 scripts/deploy-prep.py www.yourdomain.com

效果:
  将项目中所有 bidding-site.pages.dev 替换为你的真实域名
  更新：sitemap.xml、canonical URL、OG URL、JSON-LD URL、robots.txt
"""

import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = 'bidding-site.pages.dev'

# 需要替换的文件列表
FILES = [
    'index.html',
    'list.html',
    'detail.html',
    'robots.txt',
    'sitemap.xml',
    'functions/api/_wxpusher.js',
]

def main():
    if len(sys.argv) < 2:
        print('❌ 请提供你的域名')
        print('   用法: python3 scripts/deploy-prep.py xxx.pages.dev')
        sys.exit(1)

    new_domain = sys.argv[1].strip().lower()
    # 去掉 protocol 前缀
    new_domain = re.sub(r'^https?://', '', new_domain)
    # 去掉尾部斜杠
    new_domain = new_domain.rstrip('/')

    if new_domain == PLACEHOLDER:
        print('❌ 域名和占位相同，没有变化')
        sys.exit(1)

    total_changes = 0
    for rel_path in FILES:
        filepath = ROOT / rel_path
        if not filepath.exists():
            print(f'⚠️  跳过：{rel_path}（不存在）')
            continue

        content = filepath.read_text(encoding='utf-8')
        count = content.count(PLACEHOLDER)
        if count == 0:
            continue

        new_content = content.replace(PLACEHOLDER, new_domain)
        filepath.write_text(new_content, encoding='utf-8')
        total_changes += count
        print(f'  ✓ {rel_path}: {count} 处替换')

    # 也重新生成 sitemap
    print(f'\n正在重新生成 sitemap.xml...')
    import subprocess
    result = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'build-sitemap.py')],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode == 0:
        print(f'  ✓ {result.stdout.strip()}')

    # 更新 robots.txt 的 sitemap URL（因为 sitemap 生成时用了占位域名）
    robots_path = ROOT / 'robots.txt'
    if robots_path.exists():
        content = robots_path.read_text(encoding='utf-8')
        # 确保 robots.txt 中的 sitemap URL 也正确
        content = content.replace(f'Sitemap: https://{PLACEHOLDER}/sitemap.xml',
                                   f'Sitemap: https://{new_domain}/sitemap.xml')
        robots_path.write_text(content, encoding='utf-8')
        print(f'  ✓ robots.txt: sitemap URL 已更新')

    print(f'\n✅ 全部完成！共替换 {total_changes + 1} 处 URL')
    print(f'   占位域名: {PLACEHOLDER}')
    print(f'   真实域名: {new_domain}')
    print(f'\n现在可以重新部署到 Cloudflare Pages 了。')
    print(f'部署后检查：')
    print(f'  1. 首页打开 https://{new_domain}/')
    print(f'  2. API 测试 curl https://{new_domain}/api/bids')
    print(f'  3. 右侧浮窗显示正常')


if __name__ == '__main__':
    main()
