from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="render_markdown")
def render_markdown(value):
    """Format evidence for reading; sanitisation is mandatory for uploaded sources."""
    import bleach
    import markdown

    html = markdown.markdown(str(value or ""), extensions=["tables", "fenced_code"])
    safe_html = bleach.clean(
        html,
        tags={
            "p",
            "br",
            "hr",
            "strong",
            "em",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "blockquote",
            "pre",
            "code",
            "a",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
        },
        attributes={"a": ["href", "title"]},
        protocols={"https", "http", "mailto"},
        strip=True,
    )
    return mark_safe(safe_html)


@register.simple_tag
def icon(name, size=20):
    paths = {
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
        "clients": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M15 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
        "queue": '<path d="M4 4h16v16H4zM4 14h5l2 3h2l2-3h5M8 8h8"/>',
        "source": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5"/>',
        "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
        "arrow": '<path d="m9 5 7 7-7 7"/>',
        "check": '<path d="m5 12 4 4L19 6"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "alert": '<path d="m12 3 10 18H2zM12 9v4M12 17h.01"/>',
        "plus": '<path d="M12 5v14M5 12h14"/>',
        "upload": '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
        "leaf": '<path d="M20 3c-11-2-17 4-15 12 9 4 16-2 15-12ZM4 21 16 9"/>',
        "logout": '<path d="M9 4H4v16h5m6-4 4-4-4-4m-6 4h10"/>',
        "shield": '<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6z"/><path d="m8 12 3 3 5-6"/>',
        "link": '<path d="m10 13 4-4m-5 8-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2-2 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
        "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    }
    # Only static developer-owned SVG strings are marked safe.
    return format_html(
        '<svg width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>',
        size,
        size,
        mark_safe(paths.get(name, paths["source"])),
    )
