"""F-06: rendered Markdown must never carry active HTML into pages."""


import pytest
from fastapi.testclient import TestClient

from app.services.markdown_safety import sanitize_html
from app.services.project_status import render_stage_requirements

MALICIOUS_MARKDOWN = """# 恶意文档

正常段落。

<script>alert('xss')</script>

<iframe src="https://evil.example/"></iframe>

<img src="x" onerror="alert(1)">

<p onclick="steal()">带事件属性的段落</p>

<svg onload="alert(2)"><circle /></svg>

[正常链接](https://ok.example/page)

[危险链接](javascript:alert(3))

[编码危险](java&#x73;cript:alert(4))

| 列 A | 列 B |
| --- | --- |
| 值 1 | 值 2 |

```python
print("code block")
```
"""


def test_sanitize_html_removes_active_content() -> None:
    from app.services.document_catalog import render_document

    rendered = render_document({"source": MALICIOUS_MARKDOWN})
    lowered = rendered.lower()

    assert "<script" not in lowered
    assert "<iframe" not in lowered
    assert "<img" not in lowered
    assert "<svg" not in lowered
    assert "onerror" not in lowered
    assert "onload" not in lowered
    assert "onclick" not in lowered
    assert "javascript:" not in lowered
    assert "alert(" not in lowered


def test_sanitize_html_keeps_tables_code_and_safe_links() -> None:
    from app.services.document_catalog import render_document

    rendered = render_document({"source": MALICIOUS_MARKDOWN})
    lowered = rendered.lower()

    assert "<table>" in lowered
    assert "<th" in lowered
    assert "<td>" in lowered
    assert "<pre><code" in lowered
    assert "code block" in rendered
    assert 'href="https://ok.example/page"' in lowered
    assert "正常段落" in rendered


@pytest.mark.parametrize(
    "payload",
    [
        '<a href="javascript:alert(1)">x</a>',
        '<a href="data:text/html,<script>x</script>">x</a>',
        '<a href="vbscript:msgbox(1)">x</a>',
        '<a href="file:///D:/secret.txt">x</a>',
        '<div style="background:url(javascript:1)">x</div>',
        '<form action="https://evil.example/steal"><input name="p"></form>',
        '<object data="x"></object>',
        '<embed src="x">',
    ],
)
def test_sanitize_html_blocks_individual_vectors(payload: str) -> None:
    rendered = sanitize_html(f"<p>前文</p>{payload}<p>后文</p>")
    lowered = rendered.lower()

    assert "javascript:" not in lowered
    assert "<form" not in lowered
    assert "<input" not in lowered
    assert "<object" not in lowered
    assert "<embed" not in lowered
    assert "style=" not in lowered
    assert "前文" in rendered
    assert "后文" in rendered


def test_document_detail_page_renders_sanitized_markdown(monkeypatch, tmp_path) -> None:
    from app.main import app

    from app.services import document_catalog

    monkeypatch.setenv("PROJECT_STATUS_ENABLED", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "markdown-xss.db"))
    docs_dir = tmp_path / "docs"
    owner_dir = docs_dir / "owner"
    owner_dir.mkdir(parents=True)
    (owner_dir / "恶意样例.md").write_text(MALICIOUS_MARKDOWN, encoding="utf-8")
    (docs_dir / "document-status.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(document_catalog, "DOCUMENTS_DIR", docs_dir)

    catalog = document_catalog.build_document_catalog()
    document_id = catalog["documents"][0]["id"]

    with TestClient(app) as client:
        response = client.get(f"/project-status/documents/{document_id}")

    assert response.status_code == 200
    lowered = response.text.lower()
    # 断言范围限定为渲染后的文档正文；页面模板自带的静态脚本标签不属于注入内容。
    body_start = lowered.index('class="markdown-body"')
    body_end = lowered.index("</article>", body_start)
    document_body = lowered[body_start:body_end]
    assert "<table>" in document_body
    assert "<script" not in document_body
    assert "javascript:" not in document_body
    assert "onerror" not in document_body
    assert "<iframe" not in document_body


def test_stage_requirements_rendering_is_sanitized(tmp_path) -> None:
    stages_dir = tmp_path / "docs" / "requirements" / "stages"
    stages_dir.mkdir(parents=True)
    (stages_dir / "P1-账号与角色权限需求.md").write_text(
        MALICIOUS_MARKDOWN, encoding="utf-8"
    )

    rendered = render_stage_requirements("P1", project_root=tmp_path)
    lowered = rendered.lower()

    assert "<table>" in lowered
    assert "<script" not in lowered
    assert "javascript:" not in lowered
    assert "onerror" not in lowered
