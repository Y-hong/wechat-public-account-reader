# Parsing Fallbacks

WeChat article pages are large and script-heavy. The extractor should prioritize deterministic HTML parsing before using visual/OCR methods.

## Fetch Order

1. Local file read, when the input is a path.
2. Python `urllib` with browser-like headers.
3. On Windows, PowerShell `Invoke-WebRequest -UseBasicParsing` if Python fetch does not expose `js_content`.

Do not keep temporary downloaded HTML files unless debugging was explicitly requested.

## Body Extraction

Primary body container:

```html
<div id="js_content">...</div>
```

The body may contain nested `section`, `p`, `span`, and image tags. Preserve paragraph boundaries where possible, then remove WeChat tail boilerplate.

## Time Extraction

Try publication time in this order:

1. `var createTime = 'YYYY-MM-DD HH:mm'`
2. `create_time: 'YYYY-MM-DD HH:mm'`
3. JSON `"create_time": "..."`
4. `ori_create_time: 'unix_timestamp'`
5. `create_timestamp: 'unix_timestamp'`
6. URL-decoded JSON `"publish_time": unix_timestamp`

Unix timestamps should be converted to Beijing time (`UTC+08:00`) as `YYYY-MM-DD HH:mm`.

## Failure Signals

Mark the extraction as `partial` when:

- HTML was fetched but `js_content` was not found.
- `js_content` was found but cleaned text is empty.

Record warnings rather than hiding uncertainty.
