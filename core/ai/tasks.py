from . import client
from .schemas import Claims, Comparison, Triage


def extract_claims(passage):
    result, provenance = client.request("extract_claims", {"passage": passage}, Claims)
    if result is None:
        return [], provenance
    return [claim for claim in result.claims if claim.quote in passage], provenance


def compare_claims(passage_a, passage_b):
    result, provenance = client.request("compare_claims", {"a": passage_a, "b": passage_b}, Comparison)
    if result is None:
        return None, provenance
    if result.relation in {"CONTRADICTS", "SUPPORTS"} and (
        not result.quote_a or not result.quote_b or result.quote_a not in passage_a or result.quote_b not in passage_b):
        return None, "invalid"
    return result, provenance


def triage_change(old, new):
    return client.request("triage_change", {"old": old, "new": new}, Triage)
