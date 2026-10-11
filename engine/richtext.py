"""Formatted email bodies from the compose editor.

The editor sends HTML. Only simple formatting survives (fonts, sizes, bold,
italic, underline, lists, links); everything else is dropped, keeping its text.
The plain text the guardrails check is derived from the same cleaned HTML, so
what is checked is what is sent.
"""

import html
import re
from html.parser import HTMLParser

# Font choices offered in the editor, as in Gmail: label -> CSS font stack.
FONTS = {
    "Sans Serif": "Arial, Helvetica, sans-serif",
    "Serif": "'Times New Roman', Times, serif",
    "Fixed width": "'Courier New', Courier, monospace",
    "Wide": "'Arial Black', Arial, sans-serif",
    "Narrow": "'Arial Narrow', Arial, sans-serif",
    "Comic Sans MS": "'Comic Sans MS', 'Comic Sans', cursive",
    "Garamond": "Garamond, 'Times New Roman', serif",
    "Georgia": "Georgia, serif",
    "Tahoma": "Tahoma, Verdana, sans-serif",
    "Trebuchet MS": "'Trebuchet MS', Arial, sans-serif",
    "Verdana": "Verdana, Geneva, sans-serif",
}
SIZES = {"Small": "2", "Normal": "3", "Large": "4", "Huge": "6"}

ALLOWED = {
    "b": (), "strong": (), "i": (), "em": (), "u": (), "br": (), "div": ("style",), "p": ("style",),
    "span": ("style",), "font": ("face", "size"), "ul": (), "ol": (), "li": (), "a": ("href",),
    "blockquote": (),
}
VOID = {"br"}
DROP_WITH_CONTENT = {"script", "style", "head", "title", "xml", "meta", "iframe", "object"}
STYLE_PROPS = {"font-family", "font-size", "font-weight", "font-style", "text-decoration"}
BLOCK = {"div", "p", "li", "ul", "ol", "blockquote"}


def _clean_style(value):
    kept = []
    for decl in value.split(";"):
        prop, _, val = decl.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        if prop in STYLE_PROPS and val and not re.search(r"url\(|expression|[<>]", val, re.I):
            kept.append(f"{prop}: {val}")
    return "; ".join(kept)


class _Sanitiser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.open, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_WITH_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED:
            return
        kept = []
        for name, value in attrs:
            if name not in ALLOWED[tag] or value is None:
                continue
            if name == "style":
                value = _clean_style(value)
            elif name == "href" and not re.match(r"(?i)(https?:|mailto:)", value.strip()):
                continue
            elif name == "size" and value not in SIZES.values():
                continue
            if value:
                kept.append(f' {name}="{html.escape(value, quote=True)}"')
        self.out.append(f"<{tag}{''.join(kept)}>")
        if tag not in VOID:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in DROP_WITH_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in ALLOWED or tag in VOID or tag not in self.open:
            return
        while self.open:
            last = self.open.pop()
            self.out.append(f"</{last}>")
            if last == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self):
        return "".join(self.out) + "".join(f"</{t}>" for t in reversed(self.open))


def sanitise(markup):
    parser = _Sanitiser()
    parser.feed(markup or "")
    parser.close()
    return parser.result().strip()


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.lists = [], []

    def _newline(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")
        elif tag in ("ul", "ol"):
            self._newline()
            self.lists.append([tag, 0])
        elif tag == "li":
            self._newline()
            if self.lists:
                self.lists[-1][1] += 1
                kind, n = self.lists[-1]
                self.parts.append(f"{n}. " if kind == "ol" else "- ")
        elif tag in BLOCK:
            self._newline()

    def handle_endtag(self, tag):
        if tag in ("ul", "ol") and self.lists:
            self.lists.pop()
        if tag in BLOCK:
            self._newline()

    def handle_data(self, data):
        self.parts.append(data)


def to_text(markup):
    parser = _Text()
    parser.feed(markup or "")
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def from_text(text):
    """Plain text (templates, older drafts) as editor HTML, one div per line."""
    lines = (text or "").split("\n")
    return "".join(f"<div>{html.escape(line, quote=False) or '<br>'}</div>" for line in lines)


def email_html(markup):
    """The body as sent: wrapped with a default font so it reads like Gmail's."""
    return f'<div style="font-family: {FONTS["Sans Serif"]};">{markup}</div>'
