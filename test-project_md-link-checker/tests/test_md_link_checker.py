"""Tests for Markdown Dead Link Checker."""

import pytest
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from md_link_checker import (
    extract_links, collect_files, check_link, LinkResult, generate_report
)


# ─── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_md(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("""# Test

Valid links:
- [GitHub](https://github.com)
- [Python](https://python.org)

Invalid link:
- [Broken](https://example.invalid/nonexistent)

Local link:
- [About](./about.md)

Anchor and mailto (should be skipped):
- [Section](#intro)
- [Mail](mailto:test@test.com)
""", encoding='utf-8')
    return md


@pytest.fixture
def sample_md_with_image(tmp_path):
    """Markdown with image links (should be filtered)."""
    md = tmp_path / "images.md"
    md.write_text("""# Images
![Logo](/images/logo.png)
![Photo](https://example.com/photo.jpg)
- [Normal link](https://example.com)
""", encoding='utf-8')
    return md


# ─── Test: Link Extraction ─────────────────────────────────────

class TestExtractLinks:
    def test_extracts_all_valid_links(self, sample_md):
        links = extract_links(sample_md)
        # Should extract 4 links (skip anchor and mailto)
        assert len(links) == 4
        urls = [l['url'] for l in links]
        assert 'https://github.com' in urls
        assert 'https://python.org' in urls
        assert 'https://example.invalid/nonexistent' in urls
        assert './about.md' in urls

    def test_filters_image_links(self, sample_md_with_image):
        links = extract_links(sample_md_with_image)
        assert len(links) == 1  # Only the normal link
        assert links[0]['url'] == 'https://example.com'

    def test_handles_empty_file(self, tmp_path):
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding='utf-8')
        links = extract_links(empty)
        assert len(links) == 0

    def test_handles_link_with_line_numbers(self, sample_md):
        links = extract_links(sample_md)
        for l in links:
            assert l['line'] > 0
            assert 'test.md' in l['file']


# ─── Test: File Collection ─────────────────────────────────────

class TestCollectFiles:
    def test_collects_md_files_from_directory(self, tmp_path):
        (tmp_path / "a.md").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.md").write_text("")
        files = collect_files([str(tmp_path)])
        assert len(files) == 2

    def test_uses_default_glob(self, tmp_path):
        original_cwd = Path.cwd()
        try:
            Path.chdir(tmp_path)
            (tmp_path / "test.md").write_text("")
            files = collect_files([])  # No paths = default glob
            assert len(files) >= 1
        finally:
            Path.chdir(original_cwd)


# ─── Test: Link Checking ───────────────────────────────────────

class TestCheckLink:
    def test_local_file_exists(self, tmp_path):
        target = tmp_path / "other.md"
        target.write_text("exists")
        result = check_link({
            'url': './other.md',
            'file': str(tmp_path / "test.md"),
            'line': 1
        })
        assert result.status_code == 200
        assert result.is_valid

    def test_local_file_not_found(self, tmp_path):
        result = check_link({
            'url': './nonexistent.md',
            'file': str(tmp_path / "test.md"),
            'line': 1
        })
        assert result.status_code == 404

    def test_skips_non_http_anchors(self):
        result = check_link({
            'url': '#section',
            'file': 'test.md',
            'line': 1
        })
        assert result.error == "skipped"

    def test_handles_timeout_gracefully(self):
        """Connect to a non-routable IP to test timeout handling."""
        result = check_link({
            'url': 'http://10.255.255.1/test',
            'file': 'test.md',
            'line': 1
        }, timeout=2)
        assert result.error is not None  # Should timeout or fail


# ─── Test: Report Generation ───────────────────────────────────

class TestGenerateReport:
    def test_reports_all_valid(self, capsys):
        results = [
            LinkResult(url='https://ok.com', file='a.md', line=1,
                      status_code=200, response_time=0.1),
        ]
        all_ok = generate_report(results)
        assert all_ok is True

    def test_reports_invalid_links(self, capsys):
        results = [
            LinkResult(url='https://ok.com', file='a.md', line=1,
                      status_code=200, response_time=0.1),
            LinkResult(url='https://bad.com', file='a.md', line=2,
                      status_code=404, error='Not Found'),
        ]
        all_ok = generate_report(results)
        assert all_ok is False

    def test_outputs_json_file(self, tmp_path):
        output = tmp_path / "report.json"
        results = [
            LinkResult(url='https://ok.com', file='a.md', line=1,
                      status_code=200, response_time=0.1),
        ]
        generate_report(results, str(output))
        assert output.exists()
        data = json.loads(output.read_text())
        assert data['summary']['total'] == 1
        assert data['summary']['valid'] == 1


# ─── Integration Test ──────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline(self, tmp_path):
        """Test extract → check → report pipeline with real files."""
        # Create test markdown with a real link and a broken one
        md_file = tmp_path / "readme.md"
        md_file.write_text("""# Test Doc
- [Real](https://httpbin.org/status/200)
- [Real Redirect](https://httpbin.org/redirect-to?url=https://example.com)
- [Local](./local.md)
""", encoding='utf-8')

        # Create local target
        local = tmp_path / "local.md"
        local.write_text("local exists")

        # Run pipeline
        links = extract_links(md_file)
        assert len(links) == 3

        results = [check_link(l) for l in links]
        valid = [r for r in results if r.is_valid]
        
        # At least the local file and httpbin should be valid
        assert len(valid) >= 1

        # Generate report
        output = tmp_path / "report.json"
        all_ok = generate_report(results, str(output))
        assert output.exists()
