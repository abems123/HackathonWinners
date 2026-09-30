from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import authz
from .domain.effective import effective_pins
from .domain.scope import matches, scope_reason
from .forms import ActionForm, ProfileForm, UploadForm
from .models import AuditEvent, Client, Doubt, Layer, Pin, Source, Topic, User
from .services.actions import perform, update_profile
from .services.ripple import upload_version


def client_summary(client, pins):
    active, _, _ = effective_pins(pins, client.pk, client.profile)
    counts = Counter(p.status for p in active)
    client.pin_count = len(active)
    client.review_count = sum(value for key, value in counts.items() if key != "CONFIRMED")
    client.confirmed_count = counts["CONFIRMED"]
    client.layers = [layer for layer in Layer.objects.all() if matches(layer.scope_rule, client.profile)]
    return client


def visible_events(user):
    pins = authz.pins_for(user).values_list("pk", flat=True)
    sources = authz.sources_for(user).values_list("pk", flat=True)
    clients = authz.clients_for(user).values_list("pk", flat=True)
    return AuditEvent.objects.filter(Q(pin_id__in=pins) | Q(source_id__in=sources) | Q(client_id__in=clients)).select_related("actor", "pin", "source", "client")


@login_required
def home(request):
    pins = list(authz.pins_for(request.user).select_related("source", "version", "layer", "client", "base", "confirmed_by"))
    clients = [client_summary(c, pins) for c in authz.clients_for(request.user).order_by("name")]
    counts = Counter(p.status for p in pins if not p.superseded_by_id and not p.excluded)
    return render(request, "core/home.html", {"section": "overview", "clients": clients,
        "review_count": sum(v for k, v in counts.items() if k != "CONFIRMED"),
        "confirmed_count": counts["CONFIRMED"], "source_count": authz.sources_for(request.user).count(),
        "queue": authz.queue_for(request.user)[:4], "events": visible_events(request.user)[:5]})


@login_required
def clients(request):
    pins = list(authz.pins_for(request.user))
    rows = [client_summary(c, pins) for c in authz.clients_for(request.user).order_by("name")]
    country = request.GET.get("country", "")
    if country in {"BE", "NL", "LU"}:
        rows = [c for c in rows if c.profile.get("country") == country]
    return render(request, "core/clients.html", {"section": "clients", "clients": rows, "country": country})


def get_client(user, pk):
    client = get_object_or_404(Client, pk=pk)
    authz.require(authz.can_read_client(user, client))
    return client


@login_required
def client_detail(request, pk):
    client = get_client(request.user, pk)
    pins = list(authz.pins_for(request.user))
    client_summary(client, pins)
    rows = []
    for topic in Topic.objects.all():
        active, _, _ = effective_pins([p for p in pins if p.topic_id == topic.pk], client.pk, client.profile)
        counts = Counter(p.status for p in active)
        rows.append({"topic": topic, "total": len(active), "confirmed": counts["CONFIRMED"],
                     "reviews": sum(v for k, v in counts.items() if k != "CONFIRMED")})
    return render(request, "core/client.html", {"section": "clients", "client": client, "topics": rows,
        "events": visible_events(request.user).filter(Q(client=client) | Q(pin__client=client))[:5]})


@login_required
def topic_detail(request, pk, slug):
    client = get_client(request.user, pk)
    topic = get_object_or_404(Topic, slug=slug)
    pins = list(authz.pins_for(request.user).filter(topic=topic).select_related("source", "version", "layer", "client", "confirmed_by", "base"))
    active, excluded, superseded = effective_pins(pins, client.pk, client.profile)
    for pin in excluded:
        pin.scope_explanation = "Marked not applicable for this client" if pin.excluded else scope_reason(pin.layer.scope_rule, client.profile)
    expert = User.objects.filter(team__name__endswith=client.profile.get("country", ""), is_active=True).exclude(role="SYSTEM").first()
    return render(request, "core/topic.html", {"section": "clients", "client": client, "topic": topic,
        "pins": active, "excluded": excluded, "superseded": superseded, "expert": expert,
        "topics": Topic.objects.all()})


@login_required
def queue(request):
    kind = request.GET.get("kind", "")
    doubts = authz.queue_for(request.user)
    if kind in {"SOURCE_CHANGED", "POSSIBLE_CONFLICT", "QUESTION", "EXPIRED", "AI_SUGGESTED", "SOURCE_OUTDATED", "CONFLICT"}:
        doubts = doubts.filter(kind=kind)
    return render(request, "core/queue.html", {"section": "queue", "doubts": doubts, "kind": kind})


def prepare_action_form(user, pin, data=None, initial=None, expert_only=False):
    form = ActionForm(data, initial=initial)
    actions = {"answer"} if expert_only else {"ask", "source_outdated"}
    if not expert_only and authz.can_change_pin(user, pin):
        actions |= {"confirm", "supersede", "dismiss", "escalate"}
        if pin.client_id:
            actions.add("does_not_apply")
    if not expert_only and pin.layer_id:
        actions.add("add_exception")
    form.fields["action"].choices = [(value, label) for value, label in form.fields["action"].choices if value in actions]
    form.fields["related_pin"].queryset = authz.pins_for(user).filter(topic=pin.topic, layer=pin.layer, client=pin.client).exclude(pk=pin.pk)
    form.fields["expert"].queryset = User.objects.filter(is_active=True).exclude(role="SYSTEM").order_by("first_name")
    return form


@login_required
def pin_detail(request, pk):
    pin = get_object_or_404(Pin, pk=pk)
    authz.require(authz.can_read_pin(request.user, pin))
    client_id = request.GET.get("client")
    client = get_client(request.user, client_id) if client_id else pin.client
    if client and pin.client_id:
        authz.require(pin.client_id == client.pk)
    form = prepare_action_form(request.user, pin, initial={"version_id": pin.source.latest.pk})
    return render(request, "core/pin.html", {"section": "sources", "pin": pin, "client": client, "form": form,
        "latest": pin.source.latest, "doubts": pin.doubts.filter(status="OPEN"),
        "events": visible_events(request.user).filter(pin=pin)[:12]})


@login_required
def doubt_detail(request, pk):
    doubt = get_object_or_404(Doubt, pk=pk)
    authz.require(authz.can_read_doubt(request.user, doubt))
    restricted = not authz.can_read_pin(request.user, doubt.pin)
    form = prepare_action_form(request.user, doubt.pin, expert_only=restricted,
                              initial={"action": "answer" if restricted else "confirm", "version_id": doubt.pin.source.latest.pk})
    return render(request, "core/doubt.html", {"section": "queue", "doubt": doubt, "pin": doubt.pin,
        "form": form, "restricted": restricted, "can_resolve": authz.can_resolve_doubt(request.user, doubt)})


@login_required
@require_POST
def action(request, pk):
    pin = get_object_or_404(Pin, pk=pk)
    doubt_id = request.POST.get("doubt_id")
    doubt = get_object_or_404(Doubt, pk=doubt_id, pin=pin) if doubt_id else None
    restricted = not authz.can_read_pin(request.user, pin)
    authz.require(not restricted or (doubt is not None and authz.can_read_doubt(request.user, doubt)))
    form = prepare_action_form(request.user, pin, request.POST, expert_only=restricted)
    target = reverse("doubt", args=[doubt.pk]) if doubt else reverse("pin", args=[pin.pk])
    if form.is_valid():
        try:
            client = get_client(request.user, request.POST["client_id"]) if request.POST.get("client_id") else None
            perform(request.user, pin, doubt=doubt, client=client, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Your decision was saved and added to the audit trail.")
            if request.headers.get("HX-Request"):
                return HttpResponse(headers={"HX-Redirect": target})
            return redirect(target)
    return render(request, "core/action_error.html", {"form": form, "target": target}, status=422)


@login_required
def sources(request):
    rows = authz.sources_for(request.user).select_related("owner", "layer", "client").order_by("title")
    topic = request.GET.get("topic", "")
    if topic:
        rows = rows.filter(topics__slug=topic)
    return render(request, "core/sources.html", {"section": "sources", "sources": rows, "topics": Topic.objects.all(), "topic_filter": topic})


@login_required
def source_detail(request, pk):
    source = get_object_or_404(Source, pk=pk)
    authz.require(authz.can_read_source(request.user, source))
    return render(request, "core/source.html", {"section": "sources", "source": source, "latest": source.latest,
        "versions": source.versions.order_by("-number"), "can_upload": authz.can_upload_version(request.user, source),
        "pins": authz.pins_for(request.user).filter(source=source), "events": visible_events(request.user).filter(source=source)[:10]})


@login_required
def upload(request, pk):
    source = get_object_or_404(Source, pk=pk)
    authz.require(authz.can_upload_version(request.user, source))
    form = UploadForm(request.POST or None, request.FILES or None, initial={"effective_from": timezone.localtime().strftime("%Y-%m-%dT%H:%M")})
    if request.method == "POST" and form.is_valid():
        version, summary = upload_version(request.user, source, form.cleaned_data["content"], form.cleaned_data["effective_from"], form.cleaned_data["effective_to"])
        return render(request, "core/ripple.html", {"section": "sources", "source": source, "version": version, "summary": summary})
    return render(request, "core/upload.html", {"section": "sources", "source": source, "form": form})


@login_required
def profile(request, pk):
    client = get_client(request.user, pk)
    form = ProfileForm(request.POST or None, initial={**client.profile, "payroll_close": client.payroll_close})
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        update_profile(request.user, client, {"country": values["country"], "pc": values["pc"]}, values["payroll_close"], values["reason"])
        messages.success(request, "Client profile updated. Dependent passages are flagged for review.")
        return redirect("client", pk=client.pk)
    return render(request, "core/profile.html", {"section": "clients", "client": client, "form": form})


@login_required
def activity(request):
    return render(request, "core/activity.html", {"section": "activity", "events": visible_events(request.user)[:100]})


@login_required
def people(request):
    import json
    from django.conf import settings
    directory = json.loads((settings.BASE_DIR / "data/people.json").read_text(encoding="utf-8"))
    return render(request, "core/people.html", {"section": "people", "people": directory})
