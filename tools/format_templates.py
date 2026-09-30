"""Keep template control tags intact while making source files reviewable."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def run():
    for path in (ROOT / "core/templates").rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        # Newlines between HTML tags are insignificant; Django control tags stay intact.
        content = re.sub(
            r">(?=<(?:div|section|aside|article|header|footer|nav|main|form|details|h[123]|p|blockquote)\b)",
            ">\n",
            content,
        )
        content = re.sub(r"(?<=[>])(?={% (?:block|endblock|for|endfor|if|endif)\b)", "\n", content)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    run()
