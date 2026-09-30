from .scope import matches


def effective_pins(pins, client_id, profile):
    active, excluded, superseded = [], [], []
    for pin in pins:
        if pin.client_id and pin.client_id != client_id:
            continue
        if pin.superseded_by_id:
            superseded.append(pin)
        elif pin.excluded or (pin.layer_id and not matches(pin.layer.scope_rule, profile)):
            excluded.append(pin)
        else:
            active.append(pin)
    active.sort(key=lambda pin: (not bool(pin.base_id), pin.pk))
    return active, excluded, superseded
