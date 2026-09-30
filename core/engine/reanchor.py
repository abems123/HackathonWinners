from dataclasses import dataclass
from rapidfuzz.fuzz import ratio
from core.domain.passage import anchor, normalize


@dataclass
class Match:
    outcome: str
    quote: str = ""
    prefix: str = ""
    suffix: str = ""


def reanchor(prefix, quote, suffix, content):
    count = content.count(quote)
    if count > 1:
        return Match("AMBIGUOUS")
    if count == 1:
        new_prefix, new_quote, new_suffix = anchor(content, quote)
        outcome = (
            "UNCHANGED"
            if (normalize(prefix), normalize(suffix))
            == (normalize(new_prefix), normalize(new_suffix))
            else "CONTEXT_CHANGED"
        )
        return Match(outcome, new_quote, new_prefix, new_suffix)
    candidates = [part.strip() for part in content.split("\n\n") if part.strip()]
    scored = sorted(
        [(ratio(normalize(quote), normalize(part)) / 100, part) for part in candidates],
        reverse=True,
    )
    if not scored or scored[0][0] < 0.75:
        return Match("DELETED")
    if len(scored) > 1 and scored[1][0] >= 0.75 and scored[0][0] - scored[1][0] < 0.05:
        return Match("AMBIGUOUS")
    new_prefix, new_quote, new_suffix = anchor(content, scored[0][1])
    return Match("MODIFIED", new_quote, new_prefix, new_suffix)
