---
name: wechat-public-account-reader
description: Read public WeChat Official Account article links, extracting structured metadata, body text, paragraphs, images, and timestamps for downstream agent training or analysis.
---

# WeChat Public Account Reader

Use this skill when the user provides one or more public WeChat Official Account article URLs such as `https://mp.weixin.qq.com/s/...` and wants the content extracted for downstream agent training, dataset construction, or analysis.

This skill is only a reader/extractor. Do not perform editor, compliance, topic recommendation, investment analysis, or author-style analysis unless the user separately asks for those tasks.

## Workflow

1. Run `scripts/extract_wechat_article.py` on the supplied URL or local HTML file.
2. Prefer `jsonl` output when the result will feed another agent or dataset pipeline.
3. Use `json` when the user wants a readable structured object for a small batch.
4. Use `markdown` only when the user wants a human-readable extraction report.
5. Do not persist downloaded article HTML unless the user asks for archival or debugging. The script uses temporary files for URL fetches and deletes them automatically.

## Commands

Single URL as JSON:

```bash
python scripts/extract_wechat_article.py "https://mp.weixin.qq.com/s/..." --format json
```

Multiple URLs as JSONL:

```bash
python scripts/extract_wechat_article.py "https://mp.weixin.qq.com/s/..." "https://mp.weixin.qq.com/s/..." --format jsonl --output articles.jsonl
```

Local HTML:

```bash
python scripts/extract_wechat_article.py article.html --format json
```

Include cleaned article HTML for layout-sensitive downstream processing:

```bash
python scripts/extract_wechat_article.py "https://mp.weixin.qq.com/s/..." --include-html --format json
```

## Output

The script returns machine-friendly records with fields such as:

- `source_type`
- `url`
- `title`
- `author`
- `account_name`
- `publish_time`
- `description`
- `cover_image`
- `content_text`
- `content_html`
- `text_len`
- `image_count`
- `image_urls`
- `paragraphs`
- `extraction_status`
- `extraction_method`
- `warnings`

See `references/output_schema.md` for the full schema.

## Parsing Notes

WeChat article pages are large and contain substantial scripts. The primary body is usually inside `id="js_content"`. Publication time can appear as `var createTime`, `create_time`, `ori_create_time`, `create_timestamp`, or URL-encoded `publish_time`.

See `references/parsing_fallbacks.md` before modifying extractor behavior.

## Data Handling

When preparing data for training or downstream agents:

- Preserve the original `url` for provenance.
- Prefer `jsonl` for batches.
- Keep `warnings` and `extraction_method`; they are useful for quality filtering.
- Do not commit full downloaded article HTML or large extracted corpora unless the user explicitly asks.
