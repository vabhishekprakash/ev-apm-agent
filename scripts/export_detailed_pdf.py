"""Export docs/detailed_document.md to docs/detailed_document.pdf.

Offline toolchain: python-markdown -> print-styled HTML -> headless Chromium
(Playwright) page.pdf(). Re-run after any edit to the markdown source:

    py scripts/export_detailed_pdf.py
"""

from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "detailed_document.md"
OUT = ROOT / "docs" / "detailed_document.pdf"

CSS = """
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt;
       line-height: 1.55; color: #1a1a1a; max-width: 100%; }
h1 { font-family: Arial, Helvetica, sans-serif; font-size: 19pt;
     border-bottom: 2px solid #1a1a1a; padding-bottom: 6px; }
h2 { font-family: Arial, Helvetica, sans-serif; font-size: 13.5pt;
     margin-top: 22px; border-bottom: 1px solid #999; padding-bottom: 3px; }
code { font-family: Consolas, monospace; font-size: 9.5pt;
       background: #f2f2f2; padding: 0 3px; }
pre { background: #f5f5f5; border: 1px solid #ddd; padding: 10px;
      font-size: 8.5pt; line-height: 1.35; overflow-x: hidden;
      white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%; font-size: 10pt; }
th, td { border: 1px solid #888; padding: 4px 8px; text-align: left; }
th { background: #eee; font-family: Arial, sans-serif; }
strong { color: #000; }
em { color: #333; }
hr { border: none; border-top: 1px solid #bbb; }
"""


def main() -> None:
    body = markdown.markdown(
        SRC.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code"])
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>" \
           f"<body>{body}</body></html>"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        page.pdf(path=str(OUT), format="A4", print_background=True,
                 margin={"top": "18mm", "bottom": "18mm",
                         "left": "16mm", "right": "16mm"})
        browser.close()
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
