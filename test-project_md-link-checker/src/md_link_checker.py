#!/usr/bin/env python3
"""Markdown Dead Link Checker - CLI tool to detect broken links in markdown files."""

import re
import sys
import time
import json
import glob
import threading
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional

try:
    import requests
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    # Fallback rich mock
    class Console:
        def print(self, *a, **kw): print(*a)
    class Table:
        def __init__(self, *a, **kw): pass
        def add_column(self, *a, **kw): pass
        def add_row(self, *a, **kw): pass
    class Progress:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def add_task(self, *a, **kw): return 0
        def update(self, *a, **kw): pass

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


# ─── Data Structures ────────────────────────────────────────────

@dataclass
class LinkResult:
    url: str
    file: str
    line: int
    status_code: Optional[int] = None
    response_time: float = 0.0
    error: Optional[str] = None
    final_url: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 400

    @property
    def is_redirect(self) -> bool:
        return self.status_code is not None and 300 <= self.status_code < 400

    @property
    def status_tag(self) -> str:
        if self.error:
            return f"❌ {self.error}"
        if self.is_valid:
            return f"✅ {self.status_code}"
        if self.is_redirect:
            return f"↪️ {self.status_code}"
        return f"❌ {self.status_code}"


# ─── Link Extraction ───────────────────────────────────────────

LINK_PATTERN = re.compile(r'(?<!!)\[([^\]]*)\]\(([^)]+)\)')

def extract_links(file_path: Path) -> List[dict]:
    """Extract all markdown links from a file."""
    links = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                for match in LINK_PATTERN.finditer(line):
                    url = match.group(2).strip()
                    # Skip anchors and mailto
                    if url.startswith('#') or url.startswith('mailto:'):
                        continue
                    links.append({
                        'url': url,
                        'file': str(file_path),
                        'line': line_no
                    })
    except Exception as e:
        log.warning(f"无法读取文件 {file_path}: {e}")
    return links


def collect_files(paths: List[str], pattern: str = '**/*.md') -> List[Path]:
    """Collect all markdown files from paths/patterns."""
    files = set()
    for p in paths:
        path = Path(p)
        if path.is_file() and path.suffix == '.md':
            files.add(path)
        elif path.is_dir():
            files.update(path.rglob('*.md'))
        else:
            # Treat as glob pattern
            files.update(Path().glob(p))
    # If no paths given, use default pattern
    if not paths:
        files.update(Path().glob(pattern))
    return sorted(files)


# ─── Link Checking ─────────────────────────────────────────────

def check_link(link: dict, timeout: int = 10, retry: int = 1) -> LinkResult:
    """Check a single link's validity."""
    url = link['url']
    result = LinkResult(url=url, file=link['file'], line=link['line'])

    # Skip anchor-only links (#section)
    if url.startswith('#'):
        result.error = "skipped"
        return result

    # Skip non-http(s) links
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https', ''):
        result.error = "skipped"
        return result
    if not parsed.scheme:
        # Relative path - check if file exists locally
        base = Path(link['file']).parent
        target = (base / url).resolve()
        if target.exists():
            result.status_code = 200
            result.response_time = 0
        else:
            result.status_code = 404
            result.error = "local file not found"
        return result

    # HTTP check with retry
    headers = {
        'User-Agent': 'MD-Link-Checker/1.0',
        'Accept': 'text/html,application/xhtml+xml,*/*'
    }

    for attempt in range(retry + 1):
        try:
            start = time.time()
            resp = requests.head(url, timeout=timeout, headers=headers,
                               allow_redirects=True)
            result.response_time = time.time() - start
            result.status_code = resp.status_code
            result.final_url = resp.url
            break
        except requests.Timeout:
            result.error = "timeout"
            if attempt < retry:
                time.sleep(1)
        except requests.ConnectionError:
            result.error = "connection failed"
            break
        except requests.RequestException as e:
            result.error = str(e)[:50]
            break

    return result


# ─── Report Output ─────────────────────────────────────────────

def generate_report(results: List[LinkResult], output_file: Optional[str] = None):
    """Generate and display the link check report."""
    valid = [r for r in results if r.is_valid]
    invalid = [r for r in results if not r.is_valid and r.error != 'skipped']
    skipped = [r for r in results if r.error == 'skipped']
    redirects = [r for r in results if r.is_redirect]

    # Terminal report
    console = Console()
    
    summary = Table(title="📊 检测摘要")
    summary.add_column("指标", style="cyan")
    summary.add_column("数量", justify="right")
    summary.add_row("总链接数", str(len(results)))
    summary.add_row("有效链接", f"{len(valid)} ✅")
    summary.add_row("重定向", f"{len(redirects)} ↪️")
    summary.add_row("失效链接", f"{len(invalid)} ❌")
    summary.add_row("已跳过", f"{len(skipped)} ⏭️")
    console.print(summary)

    if invalid:
        fail_table = Table(title="❌ 失效链接详情")
        fail_table.add_column("文件", style="dim")
        fail_table.add_column("行号", justify="right")
        fail_table.add_column("URL")
        fail_table.add_column("原因")
        for r in invalid[:20]:  # Show top 20
            fail_table.add_row(
                Path(r.file).name, str(r.line),
                r.url[:60], r.error or str(r.status_code)
            )
        console.print(fail_table)
        if len(invalid) > 20:
            console.print(f"... 还有 {len(invalid)-20} 个失效链接未显示")

    # JSON output
    if output_file:
        output = {
            'summary': {
                'total': len(results),
                'valid': len(valid),
                'invalid': len(invalid),
                'redirects': len(redirects),
                'skipped': len(skipped)
            },
            'details': [asdict(r) for r in results]
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        console.print(f"\n📄 详细报告已保存: {output_file}")

    return len(invalid) == 0


# ─── CLI Entry Point ───────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='🔗 Markdown 死链检测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('paths', nargs='*', default=[],
                       help='Markdown 文件/目录/glob 模式（默认: **/*.md）')
    parser.add_argument('--timeout', type=int, default=10,
                       help='请求超时秒数（默认: 10）')
    parser.add_argument('--retry', type=int, default=1,
                       help='失败重试次数（默认: 1）')
    parser.add_argument('--concurrency', type=int, default=10,
                       help='并发检测数（默认: 10）')
    parser.add_argument('--output', '-o', type=str,
                       help='输出 JSON 报告到文件')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Phase 1: Collect files
    console = Console()
    console.print("[bold cyan]🔍 Markdown 死链检测[/bold cyan]")
    
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task("扫描文件...")
        files = collect_files(args.paths)

    if not files:
        console.print("[yellow]未找到 Markdown 文件[/yellow]")
        sys.exit(0)

    console.print(f"📂 找到 {len(files)} 个 Markdown 文件")

    # Phase 2: Extract links
    all_links = []
    for f in files:
        links = extract_links(f)
        all_links.extend(links)

    if not all_links:
        console.print("[yellow]未找到任何链接[/yellow]")
        sys.exit(0)

    console.print(f"🔗 提取到 {len(all_links)} 个链接")

    # Phase 3: Check links concurrently
    results = []
    with Progress() as progress:
        task = progress.add_task(
            f"[cyan]检测中... 0/{len(all_links)}", total=len(all_links))
        
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {
                executor.submit(check_link, link, args.timeout, args.retry): link
                for link in all_links
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                progress.update(task, advance=1,
                              description=f"[cyan]检测中... {len(results)}/{len(all_links)}")

    # Phase 4: Report
    all_ok = generate_report(results, args.output)
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
