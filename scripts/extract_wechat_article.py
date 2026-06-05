#!/usr/bin/env python3
"""Extract structured content from public WeChat Official Account articles."""

from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


WECHAT_TAIL_MARKERS = [
    "预览时标签不可点",
    "阅读原文",
    "微信扫一扫",
    "关注该公众号",
    "继续滑动看下一个",
    "轻触阅读原文",
    "向上滑动看下一个",
    "知道了",
]


@dataclass
class ExtractedArticle:
    source_type: str = "wechat_official_account"
    url: str = ""
    title: str = ""
    author: str = ""
    account_name: str = ""
    publish_time: str = ""
    publish_time_source: str = ""
    description: str = ""
    cover_image: str = ""
    content_text: str = ""
    content_html: str = ""
    text_len: int = 0
    image_count: int = 0
    image_urls: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    extraction_status: str = "success"
    extraction_method: str = ""
    warnings: list[str] = field(default_factory=list)


def pick(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.S)
    return html.unescape(match.group(1)).strip() if match else ""


def is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def read_source(source: str) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    if not is_url(source):
        return Path(source).read_bytes().decode("utf-8", "replace"), "local_file", warnings

    raw_html = fetch_with_python(source, warnings)
    if has_js_content(raw_html):
        return raw_html, "python_urllib", warnings

    if platform.system().lower() == "windows":
        fallback = fetch_with_powershell(source, warnings)
        if fallback:
            method = "powershell_invoke_webrequest"
            return fallback, method, warnings

    warnings.append("URL fetch did not expose js_content; extraction may fail.")
    return raw_html, "python_urllib_empty_or_partial", warnings


def fetch_with_python(url: str, warnings: list[str]) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - record broad fetch failures.
        warnings.append(f"python_urllib_fetch_failed: {exc}")
        return ""


def fetch_with_powershell(url: str, warnings: list[str]) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        tmp_path = Path(tmp.name)
    try:
        command = (
            f'Invoke-WebRequest -Uri "{url}" -UseBasicParsing '
            f'-OutFile "{str(tmp_path)}"'
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=35,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            warnings.append(f"powershell_fetch_failed: {detail}")
            return ""
        return tmp_path.read_bytes().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"powershell_fetch_exception: {exc}")
        return ""
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def has_js_content(raw_html: str) -> bool:
    return 'id="js_content"' in raw_html or "id='js_content'" in raw_html


def article_html(raw_html: str) -> str:
    content = pick(r'<div[^>]+id="js_content"[^>]*>(.*?)</div>\s*</div>\s*<script', raw_html)
    if not content:
        content = pick(r'<div[^>]+id="js_content"[^>]*>(.*?)</div>', raw_html)
    return content


def clean_content_text(content: str) -> tuple[str, list[str]]:
    content = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", "", content, flags=re.S)
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.I)
    content = re.sub(r"</p>|</section>|</h[1-6]>|</div>", "\n", content, flags=re.I)
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content.replace("&nbsp;", " "))

    paragraphs: list[str] = []
    for line in re.split(r"[\r\n]+", content):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            paragraphs.append(line)

    paragraphs = remove_tail_boilerplate(paragraphs)
    return "\n".join(paragraphs).strip(), paragraphs


def remove_tail_boilerplate(paragraphs: list[str]) -> list[str]:
    cleaned = list(paragraphs)
    while cleaned and any(marker in cleaned[-1] for marker in WECHAT_TAIL_MARKERS):
        cleaned.pop()
    return cleaned


def extract_image_urls(content: str) -> list[str]:
    urls: set[str] = set()
    patterns = [
        r'data-src="([^"]+)"',
        r'src="([^"]*(?:mmbiz|qpic)[^"]*)"',
        r'data-backsrc="([^"]+)"',
    ]
    for pattern in patterns:
        for url in re.findall(pattern, content):
            urls.add(html.unescape(url))
    return sorted(urls)


def timestamp_to_beijing(value: str) -> str:
    try:
        timestamp = int(value)
    except ValueError:
        return ""
    tz = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(timestamp, tz=tz).strftime("%Y-%m-%d %H:%M")


def extract_publish_time(raw_html: str) -> tuple[str, str]:
    string_patterns = [
        (r"var createTime = '([^']+)'", "var_createTime"),
        (r"create_time:\s*'([^']+)'", "create_time"),
        (r'"create_time"\s*:\s*"([^"]+)"', "json_create_time"),
    ]
    for pattern, source in string_patterns:
        value = pick(pattern, raw_html)
        if value:
            return value, source

    timestamp_patterns = [
        (r"ori_create_time:\s*'(\d+)'", "ori_create_time"),
        (r"create_timestamp:\s*'(\d+)'", "create_timestamp"),
        (r'"publish_time"\s*:\s*(\d+)', "json_publish_time"),
    ]
    decoded = urllib.parse.unquote(raw_html)
    for text in (raw_html, decoded):
        for pattern, source in timestamp_patterns:
            value = pick(pattern, text)
            if value:
                converted = timestamp_to_beijing(value)
                if converted:
                    return converted, source
    return "", ""


def extract_account_name(raw_html: str) -> str:
    candidates = [
        pick(r'id="js_name"[^>]*>\s*([^<]+)', raw_html),
        pick(r'nickname\s*:\s*"([^"]+)"', raw_html),
        pick(r"nickname\s*:\s*'([^']+)'", raw_html),
    ]
    for candidate in candidates:
        normalized = re.sub(r"\s+", " ", candidate).strip()
        if normalized:
            return normalized
    return ""


def extract_article(source: str, include_html: bool) -> ExtractedArticle:
    raw_html, method, warnings = read_source(source)
    content = article_html(raw_html)
    text, paragraphs = clean_content_text(content)
    images = extract_image_urls(content)
    publish_time, publish_time_source = extract_publish_time(raw_html)

    article = ExtractedArticle(
        url=source if is_url(source) else "",
        title=pick(r'<meta property="og:title" content="([^"]*)"', raw_html)
        or pick(r'id="activity-name"[^>]*>\s*([^<]+)', raw_html),
        author=pick(r'<meta name="author" content="([^"]*)"', raw_html),
        account_name=extract_account_name(raw_html),
        publish_time=publish_time,
        publish_time_source=publish_time_source,
        description=pick(r'<meta name="description" content="([^"]*)"', raw_html),
        cover_image=pick(r'<meta property="og:image" content="([^"]*)"', raw_html),
        content_text=text,
        content_html=content if include_html else "",
        text_len=len(text),
        image_count=len(images),
        image_urls=images,
        paragraphs=paragraphs,
        extraction_method=method,
        warnings=warnings,
    )

    if not raw_html:
        article.extraction_status = "failed"
        article.warnings.append("No HTML content was fetched or read.")
    elif not content:
        article.extraction_status = "partial"
        article.warnings.append("Could not locate js_content article body.")
    elif not text:
        article.extraction_status = "partial"
        article.warnings.append("Article body was found but text extraction returned empty.")
    if not article.publish_time:
        article.warnings.append("Publication time not found.")
    if not article.title:
        article.warnings.append("Title not found.")

    return article


def as_dict(article: ExtractedArticle) -> dict:
    return {
        "source_type": article.source_type,
        "url": article.url,
        "title": article.title,
        "author": article.author,
        "account_name": article.account_name,
        "publish_time": article.publish_time,
        "publish_time_source": article.publish_time_source,
        "description": article.description,
        "cover_image": article.cover_image,
        "content_text": article.content_text,
        "content_html": article.content_html,
        "text_len": article.text_len,
        "image_count": article.image_count,
        "image_urls": article.image_urls,
        "paragraphs": article.paragraphs,
        "extraction_status": article.extraction_status,
        "extraction_method": article.extraction_method,
        "warnings": article.warnings,
    }


def render_markdown(articles: Iterable[ExtractedArticle]) -> str:
    chunks: list[str] = []
    for article in articles:
        chunks.append(f"## {article.title or '(untitled)'}")
        chunks.append(f"- URL: {article.url}")
        chunks.append(f"- Author: {article.author}")
        chunks.append(f"- Account: {article.account_name}")
        chunks.append(f"- Publish time: {article.publish_time}")
        chunks.append(f"- Text length: {article.text_len}")
        chunks.append(f"- Image count: {article.image_count}")
        chunks.append(f"- Status: {article.extraction_status}")
        if article.warnings:
            chunks.append(f"- Warnings: {'; '.join(article.warnings)}")
        chunks.append("")
        chunks.append(article.content_text)
        chunks.append("")
    return "\n".join(chunks).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", help="WeChat article URLs or local HTML files.")
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "markdown"],
        default="jsonl",
        help="Output format. Default: jsonl.",
    )
    parser.add_argument("--output", help="Optional output file path.")
    parser.add_argument(
        "--include-html",
        action="store_true",
        help="Include cleaned js_content HTML in the output records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    articles = [extract_article(source, args.include_html) for source in args.sources]

    if args.format == "json":
        output = json.dumps([as_dict(article) for article in articles], ensure_ascii=False, indent=2)
    elif args.format == "jsonl":
        output = "\n".join(json.dumps(as_dict(article), ensure_ascii=False) for article in articles)
    else:
        output = render_markdown(articles)

    if args.output:
        Path(args.output).write_text(output + os.linesep, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
