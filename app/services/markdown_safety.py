"""Whitelist-based sanitizer for HTML produced from project Markdown.

Document bodies are project-owned but must still be treated as untrusted input
before they are embedded with ``Markup``: raw HTML in a Markdown source could
carry scripts, event handlers, or ``javascript:`` URLs.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

ALLOWED_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "code",
        "del",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
VOID_TAGS = frozenset({"br", "hr", "embed"})
# For these tags the inner text itself is the payload; everything until the
# matching end tag must be dropped, not just the tag.
_CONTENT_SUPPRESSED_TAGS = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "template",
        "noscript",
        "textarea",
        "xmp",
        "title",
    }
)
_ALLOWED_URL_SCHEMES = frozenset({"http", "https", "mailto"})
_BLOCKED_URL_PREFIXES = ("javascript:", "vbscript:", "data:", "file:")
_ATTRIBUTE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_CLASS_PATTERN = re.compile(r"^[A-Za-z0-9_. -]*$")
_ALIGN_VALUES = frozenset({"left", "right", "center"})
_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


def _safe_href(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value or len(value) > 2048:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    lowered = value.lower()
    if lowered.startswith(_BLOCKED_URL_PREFIXES):
        return None
    if lowered.startswith("&"):
        return None
    scheme = urlsplit(value).scheme.lower()
    if scheme and scheme not in _ALLOWED_URL_SCHEMES:
        return None
    return value


def _safe_attribute_value(name: str, value: str) -> str | None:
    if name == "href":
        return _safe_href(value)
    if name == "id":
        return value.strip() if _ID_PATTERN.fullmatch(value.strip()) else None
    if name == "class":
        return value if _CLASS_PATTERN.fullmatch(value) else None
    if name == "align":
        return value if value in _ALIGN_VALUES else None
    if name in {"title", "name"}:
        return value[:300]
    return None


class _MarkdownSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._suppress_depth = 0

    def _append_attributes(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kept: list[tuple[str, str]] = []
        for raw_name, raw_value in attrs:
            name = raw_name.lower()
            if not _ATTRIBUTE_NAME_PATTERN.fullmatch(name):
                continue
            if name.startswith("on"):
                continue
            if name in {"style", "srcdoc", "formaction", "action", "background"}:
                continue
            if raw_value is None:
                continue
            safe_value = _safe_attribute_value(name, raw_value)
            if safe_value is None:
                continue
            kept.append((name, safe_value))
        self._parts.append(f"<{tag}" + "".join(
            f' {name}="{escape(value, quote=True)}"' for name, value in kept
        ) + ">")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._suppress_depth:
            if tag in _CONTENT_SUPPRESSED_TAGS and tag not in VOID_TAGS:
                self._suppress_depth += 1
            return
        if tag not in ALLOWED_TAGS:
            if tag in _CONTENT_SUPPRESSED_TAGS and tag not in VOID_TAGS:
                self._suppress_depth = 1
            return
        self._append_attributes(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._suppress_depth:
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._suppress_depth:
            self._suppress_depth -= 1
            return
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._suppress_depth:
            return
        self._parts.append(escape(data))

    def result(self) -> str:
        return "".join(self._parts)


def sanitize_html(html: str) -> str:
    """Return safe HTML: keep structure tables/code/links, drop active content."""
    source = _HTML_COMMENT_PATTERN.sub("", html or "")
    parser = _MarkdownSanitizer()
    try:
        parser.feed(source)
        parser.close()
    except (ValueError, RecursionError):
        return escape(source)
    return parser.result()
