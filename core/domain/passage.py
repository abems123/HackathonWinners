import hashlib
import re


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def passage_hash(prefix, quote, suffix):
    return hashlib.sha256("\x1f".join(map(normalize, (prefix, quote, suffix))).encode()).hexdigest()


def anchor(content, quote):
    if not quote or content.count(quote) != 1:
        raise ValueError("The selected passage must occur exactly once in the source.")
    start = content.index(quote)
    # Paragraph-local context allows unrelated paragraphs to move safely.
    before = content[:start].split("\n\n")[-1]
    after = content[start + len(quote):].split("\n\n")[0]
    return before[-100:], quote, after[:100]
