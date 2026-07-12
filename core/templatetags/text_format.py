import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_HEADER_RE = re.compile(r"^#{1,6}\s*(.+)$")
_LIST_ITEM_RE = re.compile(r"^[-*•]\s+(.+)")


def _inline_format(line):
    line = _BOLD_RE.sub(r"<strong>\1</strong>", line)
    line = _ITALIC_RE.sub(r"<em>\1</em>", line)
    return line


@register.filter(name="gemini_format")
def gemini_format(text):
    """Renders the limited markdown subset Gemini tends to emit
    (bold, italics, headers, bullet/numbered lists) as safe HTML.
    The source text is HTML-escaped before any tag is introduced,
    so raw HTML/script in the model output can never reach the page.
    """
    if not text:
        return ""

    text = escape(text)

    html_parts = []
    in_list = False
    for raw_line in text.split("\n"):
        line = raw_line.strip()

        header_match = _HEADER_RE.match(line)
        if header_match:
            line = header_match.group(1)

        list_match = _LIST_ITEM_RE.match(line)
        if list_match:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_inline_format(list_match.group(1))}</li>")
            continue

        if in_list:
            html_parts.append("</ul>")
            in_list = False

        if not line:
            continue

        if header_match:
            html_parts.append(f"<p><strong>{_inline_format(line)}</strong></p>")
        else:
            html_parts.append(f"<p>{_inline_format(line)}</p>")

    if in_list:
        html_parts.append("</ul>")

    return mark_safe("".join(html_parts))
