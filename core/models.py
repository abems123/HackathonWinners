import hashlib

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .domain.passage import passage_hash
from .domain.status import PinFacts, pin_status
from .domain.templates import explanation


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=[(x, x.title()) for x in ("CONSULTANT", "OWNER", "ADMIN", "EXPERT", "SYSTEM")],
        default="CONSULTANT",
    )
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT)

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class Layer(models.Model):
    name = models.CharField(max_length=120)
    scope_rule = models.JSONField(default=dict)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_layers")
    team = models.ForeignKey(Team, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Client(models.Model):
    name = models.CharField(max_length=160)
    sector = models.CharField(max_length=100)
    profile = models.JSONField(default=dict)
    profile_version = models.PositiveIntegerField(default=1)
    payroll_close = models.DateField()
    consultants = models.ManyToManyField(User, related_name="clients")
    initials = models.CharField(max_length=3, default="CL")
    color = models.CharField(max_length=20, default="sage")

    def __str__(self):
        return self.name


class Topic(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=250, blank=True)

    def __str__(self):
        return self.name


class Source(models.Model):
    external_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    metadata = models.JSONField(default=dict)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=40, default="Policy document")
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="sources")
    layer = models.ForeignKey(Layer, null=True, blank=True, on_delete=models.PROTECT)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT)
    topics = models.ManyToManyField(Topic)
    knowledge_channel = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(layer__isnull=False, client__isnull=True)
                    | Q(layer__isnull=True, client__isnull=False)
                ),
                name="source_one_scope",
            )
        ]

    @property
    def scope_name(self):
        return self.client.name if self.client_id else self.layer.name

    @property
    def latest(self):
        return self.versions.order_by("-number").first()

    def __str__(self):
        return self.title


class SourceVersion(models.Model):
    label = models.CharField(max_length=30, blank=True)
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    content = models.TextField()
    content_hash = models.CharField(max_length=64, editable=False)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_to = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "content_hash"], name="unique_source_content"
            ),
            models.UniqueConstraint(fields=["source", "number"], name="unique_source_version"),
        ]

    def save(self, *args, **kwargs):
        self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()
        if self.pk and SourceVersion.objects.filter(pk=self.pk).exists():
            raise ValidationError("Source versions are immutable. Upload a new version.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source.title} · v{self.number}"


class Pin(models.Model):
    title = models.CharField(max_length=180)
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="pins")
    version = models.ForeignKey(SourceVersion, on_delete=models.PROTECT)
    layer = models.ForeignKey(Layer, null=True, blank=True, on_delete=models.PROTECT)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT)
    quote = models.TextField()
    prefix = models.TextField(blank=True)
    suffix = models.TextField(blank=True)
    passage_hash = models.CharField(max_length=64)
    origin = models.CharField(max_length=20, default="HUMAN")
    confirmed_version = models.ForeignKey(
        SourceVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="confirmations"
    )
    confirmed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_profile_version = models.PositiveIntegerField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    base = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="exceptions"
    )
    base_passage_hash = models.CharField(max_length=64, null=True, blank=True)
    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="supersedes"
    )
    excluded = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(layer__isnull=False, client__isnull=True)
                    | Q(layer__isnull=True, client__isnull=False)
                ),
                name="pin_one_scope",
            )
        ]

    def save(self, *args, **kwargs):
        self.passage_hash = passage_hash(self.prefix, self.quote, self.suffix)
        super().save(*args, **kwargs)

    @property
    def scope_name(self):
        return self.client.name if self.client_id else self.layer.name

    @property
    def open_kinds(self):
        return set(self.doubts.filter(status="OPEN").values_list("kind", flat=True))

    def facts(self):
        latest = self.source.latest
        return PinFacts(
            self.origin,
            "CLIENT" if self.client_id else "LAYER",
            self.confirmed_version_id,
            latest.pk if latest and not self.superseded_by_id and not self.excluded else None,
            self.version.effective_to,
            self.valid_until,
            self.confirmed_profile_version,
            self.client.profile_version if self.client_id else None,
            self.passage_hash,
            self.base.facts() if self.base_id else None,
            self.base_passage_hash,
            frozenset(self.base.open_kinds) if self.base_id else frozenset(),
        )

    @property
    def status(self):
        return pin_status(self.facts(), self.open_kinds, timezone.now()).value

    @property
    def status_label(self):
        return {
            "CONFIRMED": "Confirmed",
            "NEEDS_REVIEW": "Needs review",
            "UNCERTAIN": "Open question",
            "CONFLICT": "Conflict",
        }[self.status]

    @property
    def explanation(self):
        return explanation(
            self.status,
            self.confirmed_by.display_name if self.confirmed_by_id else "nobody",
            self.version.number,
            self.open_kinds,
        )

    def __str__(self):
        return self.title


class Doubt(models.Model):
    pin = models.ForeignKey(Pin, on_delete=models.CASCADE, related_name="doubts")
    kind = models.CharField(max_length=30)
    reason = models.TextField()
    status = models.CharField(max_length=10, default="OPEN")
    assignee_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    assignee_team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT)
    related_pin = models.ForeignKey(
        Pin, null=True, blank=True, on_delete=models.PROTECT, related_name="related_doubts"
    )
    dedupe_key = models.CharField(max_length=150, null=True, blank=True)
    severity = models.PositiveSmallIntegerField(default=2)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True)
    ai_label = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["severity", "due_date", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(assignee_user__isnull=False, assignee_team__isnull=True)
                    | Q(assignee_user__isnull=True, assignee_team__isnull=False)
                ),
                name="doubt_one_assignee",
            ),
            models.UniqueConstraint(
                fields=["dedupe_key"], condition=Q(status="OPEN"), name="unique_open_doubt"
            ),
        ]

    @property
    def pending_with(self):
        return self.assignee_user.display_name if self.assignee_user_id else self.assignee_team.name

    @property
    def kind_label(self):
        return self.kind.replace("_", " ").capitalize()


class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events are append-only.")

    def delete(self):
        raise ValidationError("Audit events are append-only.")


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    pin = models.ForeignKey(Pin, null=True, blank=True, on_delete=models.PROTECT)
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.PROTECT)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT)
    detail = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Audit events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are append-only.")


class AiCache(models.Model):
    key = models.CharField(max_length=64, unique=True)
    task = models.CharField(max_length=40)
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20)
    output = models.JSONField()
