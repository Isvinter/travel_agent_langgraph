"""
Design Blogpost Service (template-based)

Wraps raw HTML body fragments in a complete, self-contained HTML document
with embedded CSS. Template-based — no LLM dependency, deterministic output.
"""

import re
from html import unescape
from typing import Optional


_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}

  body {{
    font-family: Georgia, "Times New Roman", serif;
    color: #3a3a3a;
    background: #fafaf7;
    max-width: 780px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
    line-height: 1.8;
    font-size: 1.05rem;
  }}

  h1 {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: #2c3e1f;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #8b9a6e;
    letter-spacing: -0.02em;
  }}

  h2 {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 1.4rem;
    font-weight: 600;
    color: #4a6741;
    margin: 1.8rem 0 0.8rem;
  }}

  h3 {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: #5a7a4a;
    margin: 1.5rem 0 0.6rem;
  }}

  p {{
    margin: 0 0 1.2rem;
  }}

  img {{
    max-width: 100%;
    height: auto;
    display: block;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }}

  figure {{
    margin: 2rem auto;
    text-align: center;
  }}

  figure img {{
    margin: 0 auto;
  }}

  figcaption {{
    margin-top: 0.6rem;
    font-size: 0.9rem;
    color: #6b7a5a;
    font-style: italic;
    line-height: 1.5;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
  }}

  blockquote {{
    margin: 1.5rem 0;
    padding: 0.8rem 1.5rem;
    border-left: 4px solid #8b9a6e;
    background: #f0f3eb;
    font-style: italic;
    color: #5a6b4a;
  }}

  ul, ol {{
    margin: 0 0 1.2rem 1.5rem;
    padding: 0;
  }}

  li {{
    margin-bottom: 0.4rem;
  }}

  strong {{
    color: #2c3e1f;
  }}

  em {{
    color: #5a7a4a;
  }}

  a {{
    color: #6b8a4e;
    text-decoration: underline;
  }}

  hr {{
    border: none;
    border-top: 1px solid #d5d9cc;
    margin: 2rem 0;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
    font-size: 0.9rem;
  }}

  th, td {{
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #d5d9cc;
    text-align: left;
  }}

  th {{
    font-weight: 600;
    color: #4a6741;
    background: #f0f3eb;
  }}

  @media (max-width: 600px) {{
    body {{
      padding: 1rem 1rem 2rem;
      font-size: 0.95rem;
    }}
    h1 {{ font-size: 1.5rem; }}
    h2 {{ font-size: 1.2rem; }}
    h3 {{ font-size: 1rem; }}
  }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _extract_title(html_body: str) -> str:
    """Extrahiert den ersten H1-Text aus dem HTML-Body."""
    match = re.search(
        r"<h1[^>]*>(.*?)</h1>", html_body, re.DOTALL | re.IGNORECASE
    )
    if match:
        title = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return unescape(title)
    return "Reisebericht"


def _add_image_captions(html_body: str) -> str:
    """Wraps <img>-Tags mit alt-Text in <figure> + <figcaption>.

    Bilder ohne alt-Text bleiben unverändert (nur <img>).
    """
    def _wrap(match: re.Match) -> str:
        tag = match.group(0)
        alt = match.group(1)
        if not alt or not alt.strip():
            return tag
        return f"<figure>{tag}<figcaption>{unescape(alt.strip())}</figcaption></figure>"

    return re.sub(
        r'<img\s[^>]*\balt="([^"]*)"[^>]*>',
        _wrap,
        html_body,
        flags=re.IGNORECASE,
    )


def design_blogpost_service(
    html_body: str,
    model: str = "",  # unused — kept for API compatibility
) -> Optional[str]:
    """Wraps raw HTML body in a styled, self-contained HTML document.

    Template-based — no LLM call, deterministic output.
    All HTML tags are preserved exactly as provided.
    Image alt-text is converted to visible <figcaption>.

    Args:
        html_body: Raw HTML fragment (h1, h2, p, img, …)
        model: Ignored (kept for backwards compatibility)

    Returns:
        Complete styled HTML document, or None if body is empty.
    """
    if not html_body or not html_body.strip():
        print("⚠️  Design: Kein HTML-Body zum Stylen vorhanden")
        return None

    body_with_captions = _add_image_captions(html_body)
    title = _extract_title(html_body)
    print(f"🎨 Applying template-based design (title: {title})")
    return _PAGE_TEMPLATE.format(title=title, body=body_with_captions)
