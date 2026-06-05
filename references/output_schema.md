# Output Schema

The extractor returns one record per article. Prefer JSONL for downstream agent training or batch processing.

## Fields

- `source_type`: Always `wechat_official_account`.
- `url`: Original article URL when the source is a URL.
- `title`: Article title from Open Graph metadata or the page title node.
- `author`: Article author from metadata.
- `account_name`: WeChat public account display name when available.
- `publish_time`: Publication time in `YYYY-MM-DD HH:mm` when available.
- `publish_time_source`: Field used to recover publication time, such as `var_createTime` or `ori_create_time`.
- `description`: Article description or teaser text from metadata.
- `cover_image`: Open Graph cover image URL.
- `content_text`: Cleaned article body text.
- `content_html`: Cleaned `js_content` HTML. Empty unless `--include-html` is passed.
- `text_len`: Character length of `content_text`.
- `image_count`: Number of unique article image URLs found in the body.
- `image_urls`: Unique article image URLs found in the body.
- `paragraphs`: Cleaned paragraph list.
- `extraction_status`: `success`, `partial`, or `failed`.
- `extraction_method`: Method used to read the source, such as `python_urllib`, `powershell_invoke_webrequest`, or `local_file`.
- `warnings`: Quality or parsing warnings.

## JSONL Example

```jsonl
{"source_type":"wechat_official_account","url":"https://mp.weixin.qq.com/s/...","title":"...","author":"...","account_name":"...","publish_time":"2026-06-02 18:45","content_text":"...","text_len":1234,"image_count":5,"image_urls":[],"paragraphs":[],"extraction_status":"success","extraction_method":"powershell_invoke_webrequest","warnings":[]}
```

## Quality Filtering

For training data, prefer records where:

- `extraction_status` is `success`.
- `title` is not empty.
- `content_text` is not empty.
- `warnings` does not contain body extraction warnings.
