import re


def sensitive_tokens(text):
    return re.findall(
        r"\d+(?:[.,:/-]\d+)*(?:\s*%|\s*(?:EUR|€))?|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
        text,
        re.I,
    )


def severity(old, new):
    return 1 if sensitive_tokens(old) != sensitive_tokens(new) else 2
