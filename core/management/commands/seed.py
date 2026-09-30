import json
from datetime import date, datetime, timezone

import yaml
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from core.domain.passage import anchor
from core.engine.invalidate import create_doubt
from core.models import AuditEvent, Client, Layer, Pin, Source, SourceVersion, Team, Topic, User

ROOT = settings.BASE_DIR
DEMO_TIME = datetime(2026, 9, 30, 9, tzinfo=timezone.utc)


def read_markdown(path):
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(front), body.strip()


class Command(BaseCommand):
    help = "Load the synthetic corpus and repeatable demonstration data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            if not settings.DEBUG:
                raise CommandError(
                    "Reset is allowed only with DJANGO_DEBUG=True on a demo database."
                )
            call_command("flush", interactive=False, verbosity=0)
        if Source.objects.exists():
            from core.ai.cache import load_fixtures

            load_fixtures()
            self.stdout.write("Seed already loaded; no data changed. Use --reset for a fresh demo.")
            return
        config = yaml.safe_load((ROOT / "seed/seed.yaml").read_text(encoding="utf-8"))
        teams = {name: Team.objects.get_or_create(name=name)[0] for name in config["teams"]}
        users = {}
        for row in config["users"]:
            row = row.copy()
            team = teams[row.pop("team")]
            user = User.objects.create_user(
                **row, team=team, password="Bron-demo-2026!", is_staff=row["role"] == "ADMIN"
            )
            if user.role == "SYSTEM":
                user.set_unusable_password()
                user.save()
            users[user.username] = user
        people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))
        for person in people:
            first, last = person["name"].split(" ", 1)
            role = (
                "OWNER"
                if person["id"] in {"p-sofie", "p-lien", "p-daan", "p-tom"}
                else "CONSULTANT"
            )
            if person["id"] == "p-anne":
                role = "EXPERT"
            user = User.objects.create_user(
                username=person["id"][2:],
                first_name=first,
                last_name=last,
                email=person["email"] or "",
                team=teams[person["team"]],
                role=role,
                is_active=person["active"],
                password="Bron-demo-2026!",
            )
            users[user.username] = user
            users[person["id"]] = user
        layers = {}
        for name, scope, owner in [
            ("Belgium", {"country": "BE"}, "sofie"),
            ("Netherlands", {"country": "NL"}, "daan"),
            ("PC 200", {"country": "BE", "pc": "200"}, "sarah"),
        ]:
            layers[name] = Layer.objects.create(
                name=name, scope_rule=scope, owner=users[owner], team=users[owner].team
            )
        clients = {}
        for row in config["clients"]:
            client = Client.objects.create(
                name=row["name"],
                sector=row["sector"],
                initials=row["initials"],
                color=row["color"],
                profile={"country": row["country"], "pc": row["pc"]},
                payroll_close=date.fromisoformat(row["close"]),
            )
            client.consultants.set([users[name] for name in row["consultants"]])
            clients[client.name] = client
        topics = {r["slug"]: Topic.objects.create(**r) for r in config["topics"]}

        def make_source(
            external_id,
            title,
            body,
            owner,
            layer=None,
            client=None,
            topic="payroll-input",
            number=1,
            label="",
            metadata=None,
            expired=False,
            source_type="Policy document",
        ):
            source = Source.objects.create(
                external_id=external_id,
                title=title,
                owner=owner,
                layer=layer,
                client=client,
                type=source_type,
                metadata=metadata or {},
            )
            source.topics.add(topics[topic])
            version = SourceVersion.objects.create(
                source=source,
                number=number,
                label=label or str(number),
                content=body,
                effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                effective_to=datetime(2026, 3, 1, tzinfo=timezone.utc) if expired else None,
            )
            return source, version

        def make_pin(
            source, version, quote, topic="payroll-input", title=None, origin="HUMAN", base=None
        ):
            prefix, quote, suffix = anchor(version.content, quote)
            pin = Pin.objects.create(
                title=title or source.title,
                source=source,
                version=version,
                quote=quote,
                prefix=prefix,
                suffix=suffix,
                topic=topics[topic],
                layer=source.layer,
                client=source.client,
                origin=origin,
                confirmed_version=version if origin == "HUMAN" else None,
                confirmed_by=source.owner if origin == "HUMAN" else None,
                confirmed_at=DEMO_TIME if origin == "HUMAN" else None,
                confirmed_profile_version=source.client.profile_version if source.client else None,
                base=base,
                base_passage_hash=base.passage_hash if base else None,
            )
            return pin

        corpus_pins = {}
        for path in sorted((ROOT / "data/documents").glob("*.md")):
            meta, body = read_markdown(path)
            external_id = meta["id"]
            topic = next(
                (
                    slug
                    for tag, slug in [
                        ("HANDOVER", "handover"),
                        ("PAYSLIP", "payslips"),
                        ("EXPENSE", "expenses"),
                        ("ABSENCE", "absences"),
                    ]
                    if tag in external_id
                ),
                "payroll-input",
            )
            owner = users.get(meta["owner"], users["marc"])
            client = clients["Brouwerij De Kroon"] if meta["client"] == "dekroon" else None
            layer = (
                None if client else layers["Netherlands" if meta["country"] == "NL" else "Belgium"]
            )
            expired = external_id in {"BE-PAY-CHK-2022", "BE-HANDOVER-2019"}
            source, version = make_source(
                external_id,
                meta["title"],
                body,
                owner,
                layer,
                client,
                topic,
                label=str(meta["version"] or "1"),
                metadata=json.loads(json.dumps(meta, default=str)),
                expired=expired,
                source_type=meta["type"].replace("_", " "),
            )
            paragraphs = body.split("\n\n")
            quote = next(
                (
                    p
                    for p in paragraphs
                    if ("Payroll input for a pay month" in p or "Payroll input for a pay" in p)
                ),
                None,
            )
            if not quote:
                quote = next(
                    (
                        p
                        for p in paragraphs
                        if (
                            "Claims must" in p
                            or "Payslips are published" in p
                            or "1." in p
                            or "None recorded." in p
                        )
                    ),
                    paragraphs[-1],
                )
            pin = make_pin(source, version, quote, topic)
            corpus_pins[external_id] = pin
            if expired:
                create_doubt(
                    pin,
                    "SOURCE_OUTDATED",
                    "Historical document with no active owner; review against the current procedure.",
                )
        create_doubt(
            corpus_pins["BE-PAY-CHK-2022"],
            "POSSIBLE_CONFLICT",
            "The old checklist says 3rd working day; the confirmed procedure says 5th.",
            corpus_pins["BE-PAY-PROC-001"],
        )
        # Calendar also supports payslips, without introducing a cross-topic conflict.
        cal = corpus_pins["BE-PAY-CAL-2026"]
        cal.source.topics.add(topics["payslips"])
        make_pin(cal.source, cal.version, cal.quote, "payslips", "September payslip calendar")
        thread = json.loads(
            (ROOT / "data/teams/TEAMS-BE-CONSULTANTS-20260922.json").read_text(encoding="utf-8")
        )
        body = "\n\n".join(
            f"{users[m['author']].display_name}: {m['text']}" for m in thread["messages"]
        )
        source, version = make_source(
            thread["id"],
            thread["title"],
            body,
            users["pieter"],
            client=clients["Brouwerij De Kroon"],
            source_type="Teams thread",
        )
        exception = make_pin(
            source,
            version,
            thread["messages"][1]["text"],
            title="Temporary deadline · De Kroon only",
            origin="AI_SUGGESTED",
            base=corpus_pins["BE-PAY-PROC-001"],
        )
        exception.valid_until = datetime(2027, 1, 1, tzinfo=timezone.utc)
        exception.save()
        create_doubt(
            exception,
            "AI_SUGGESTED",
            "7th working day until December 2026, agreed only in Teams. Sofie and Pieter must record and verify the exception.",
        )
        create_doubt(
            corpus_pins["CLIENT-DEKROON"],
            "POSSIBLE_CONFLICT",
            "Client file says no deviations recorded; Teams describes an unrecorded exception.",
            exception,
        )
        meta, body = read_markdown(ROOT / "seed/sources/telework-v1.md")
        source, version = make_source(
            meta["id"],
            meta["title"],
            body,
            users["sarah"],
            layer=layers["PC 200"],
            topic="telework",
            source_type="Sector agreement",
        )
        base = None
        for i, paragraph in enumerate(body.split("\n\n")[1:]):
            pin = make_pin(
                source,
                version,
                paragraph,
                "telework",
                "Monthly allowance" if i == 0 else paragraph.rstrip("."),
            )
            if i == 0:
                base = pin
        source, version = make_source(
            "PEETERS-EXCEPTION",
            "Garage Peeters · telework agreement",
            "Garage Peeters reimburses EUR 120.00 per month under its individual agreement.",
            users["lotte"],
            client=clients["Garage Peeters"],
            topic="telework",
        )
        make_pin(
            source,
            version,
            version.content,
            "telework",
            "Client-specific telework agreement",
            base=base,
        )
        for code, title, text, number, owner, expired in [
            (
                "CORRECTION-V3",
                "Working instructions",
                "Payroll corrections must be submitted by the 25th of the month.",
                3,
                "sarah",
                False,
            ),
            (
                "CORRECTION-V1",
                "Correction deadline BE",
                "Payroll corrections must be submitted by the 20th of the month.",
                1,
                "marc",
                True,
            ),
            (
                "CORRECTION-TEAMS",
                "Payroll BE · knowledge channel",
                "The correction deadline is the 25th. Use working instructions v3.",
                1,
                "sarah",
                False,
            ),
        ]:
            source, version = make_source(
                code,
                title,
                text,
                users[owner],
                layer=layers["Belgium"],
                topic="correction-deadline",
                number=number,
                expired=expired,
            )
            source.knowledge_channel = code == "CORRECTION-TEAMS"
            source.save()
            pin = make_pin(source, version, text, "correction-deadline")
            if expired:
                create_doubt(
                    pin,
                    "EXPIRED",
                    "The old procedure expired; owner Marc has left. Review working instructions v3.",
                )
                create_doubt(
                    pin,
                    "POSSIBLE_CONFLICT",
                    "The old deadline contradicts the current working instructions.",
                )
        # Sarah owns the correction workflow; Sofie owns the original corpus.
        layers["Belgium"].team = teams["Payroll BE"]
        layers["Belgium"].save()
        AuditEvent.objects.create(
            actor=users["system"],
            action="DEMO_SEEDED",
            detail="Synthetic corpus loaded. All people and clients are fictional.",
        )
        from core.ai.cache import load_fixtures

        load_fixtures()
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {Source.objects.count()} sources, {Pin.objects.count()} pins and {Client.objects.count()} clients."
            )
        )
