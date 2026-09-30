def explanation(status, checker, version, reasons):
    if status == "CONFIRMED":
        return f"Checked by {checker} against v{version}."
    if reasons:
        return " · ".join(reason.replace("_", " ").capitalize() for reason in sorted(reasons))
    return "The source, client profile, expiry or base passage needs a fresh human review."
