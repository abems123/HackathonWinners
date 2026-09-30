def matches(rule, profile):
    return all(profile.get(key) == value for key, value in rule.items())


def scope_reason(rule, profile):
    return "; ".join(f"{key}: {value} (client: {profile.get(key, 'not set')})"
                     for key, value in rule.items() if profile.get(key) != value)
