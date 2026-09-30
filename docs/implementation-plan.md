# Bron: implementation plan

> Companion to `README.md`, the product spec. This file covers **how** we build Bron: the stack, the fixes to the spec, and the step-by-step plan.
> **Status:** proposed. The stack is pending team confirmation (see 2.3).
> **Audience:** the implementing agent and the team (Zaky, Abdellah, Oubayye, Yaman).
> **Precedence:** `README.md` defines behaviour. Where this file disagrees with it (stack, data model, status logic, demo script), this file wins.

---

## Contents

1. [Instructions for the implementing agent](#1-instructions-for-the-implementing-agent)
2. [Stack](#2-stack)
3. [Fixes to the spec](#3-fixes-to-the-spec)
4. [Data model changes](#4-data-model-changes)
5. [Implementation plan](#5-implementation-plan)
6. [Project structure](#6-project-structure)
7. [Cut order, team split, Aikido timing](#7-cut-order-team-split-aikido-timing)
8. [Review requests](#8-review-requests)
9. [Target run commands](#9-target-run-commands)

---

## 1. Instructions for the implementing agent

- Read `README.md` sections 1 to 4, 7, 8 and 15 before writing code.
- Build in the order of [section 5](#5-implementation-plan). Finish each step, including its tests and its "done when" check, before starting the next.
- These rules from the spec are non-negotiable:
  - Status is derived at read time and never stored.
  - No code path lets AI or the system user confirm a pin or resolve a doubt.
  - Explanation lines come from templates filled with facts, never from LLM text.
  - No chatbot and no free-text search box. The client and the topic are the query.
  - Every route that takes an ID checks access to that specific resource through `core/authz.py`.
  - Only synthetic data in the repo.
- When the spec is ambiguous, pick the option that fails towards doubt (🟠), and record the choice in `docs/decisions.md`.
- A second opinion is requested on the points in [section 8](#8-review-requests). Challenge them before implementing.

---

## 2. Stack

### 2.1 Decision

**Python, Django, server-rendered templates, HTMX and Tailwind.**

Bron is mostly authentication, per-object authorization, CRUD, an audit log and a deterministic engine. The AI part is three structured calls, roughly 5% of the code, so Python's AI ecosystem is not the reason for this choice.

The reason is that Django ships the security-sensitive parts already done: sessions, CSRF protection, password hashing, ORM parameterisation and template auto-escaping. Those are the areas where the Aikido audit finds issues, and security is 10% of the score. HTMX provides the interactions the app needs (resolve buttons, partial refreshes) without a second language or an API contract.

### 2.2 Alternatives considered

| Option | Languages | Auth, CSRF, sessions | Risk on hackathon day |
|---|---|---|---|
| **Django + HTMX** (chosen) | Python only | Built in, secure defaults | Low, if the team knows Python |
| Next.js full-stack (original `README.md` plan) | TypeScript only | Auth.js plus custom glue | Medium: App Router caching and server actions are easy to get wrong under time pressure |
| FastAPI + React | Two | Built by hand | High: two build systems, an API contract, CORS, token handling |
| Streamlit | Python | Effectively none | Hurts the security score and looks like a prototype |

### 2.3 Condition

If two or more team members ship Next.js regularly, TypeScript is equally valid, and `README.md` sections 7, 13 and 14 are already written for it. Never pick a stack nobody on the team has shipped with.

### 2.4 Components

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | Django 5.2 LTS, one app called `core` so migrations cannot conflict across apps |
| UI | Django templates, HTMX 2, Tailwind through the standalone CLI (no Node toolchain) |
| Database | SQLite by default; Postgres through `DATABASE_URL` (dj-database-url) |
| Input validation | Django forms on every POST (replaces zod in the spec) |
| Passwords | Django's default hasher, or Argon2 through `argon2-cffi` (replaces bcrypt in the spec) |
| Re-anchoring | rapidfuzz |
| AI | `google-genai` with `vertexai=True`, Gemini on Vertex AI in `europe-west1`. Do not use the deprecated `vertexai` generative-models SDK. |
| AI output schemas | pydantic v2 |
| Seed files | Markdown with YAML front matter (PyYAML) |
| Tests and lint | pytest, pytest-django, ruff |
| Time zone | `USE_TZ = True`, `TIME_ZONE = "Europe/Brussels"`; all datetimes are timezone-aware |
| Security audit | Aikido AI Code Audit |

### 2.5 Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Session signing | none; required |
| `DJANGO_DEBUG` | Debug mode | `False` |
| `DATABASE_URL` | Database connection | `sqlite:///db.sqlite3` |
| `AI_MODE` | `cache` (offline, from `seed/ai-cache.json`) or `live` | `cache` |
| `GCP_PROJECT`, `GCP_LOCATION` | Vertex AI project and region | `GCP_LOCATION=europe-west1` |
| `GEMINI_MODEL` | Model name, never hard-coded | none; required only in `live` mode |

Credentials use Application Default Credentials (`gcloud auth application-default login`). A service-account key file must never enter the repo.

---

## 3. Fixes to the spec

Found by reviewing `README.md` against the implementation. Fixes 3.1 to 3.5 would cost points if left in.

### 3.1 Exception pins don't fail safe

**Problem.** `pinStatus` checks the exception pin's own source version. But an exception also depends on the layer passage it modifies. If the ripple job fails, Garage Peeters' telework exception stays 🟢 after the sector amount changed. That is exactly the silent false trust the design claims cannot happen.

**Fix.** An exception pin stores `base_passage_hash`: a hash of the base pin's normalised prefix, quote and suffix, taken when the exception is confirmed. The exception's status additionally requires:
- the base pin's own assumptions hold (so a base pin with a pending newer source version turns the exception 🟠), and
- the base pin's current passage hash equals `base_passage_hash`.

Using a hash rather than a version ID means an auto-carried, unchanged base passage does not reopen the exception, while a modified one does.

### 3.2 Status order hides broken assumptions

**Problem.** The spec's `pinStatus` returns 🟡 Uncertain for an open question *before* re-checking assumptions. A pin with an open question and a broken version assumption shows 🟡 instead of 🟠.

**Fix.** Check broken assumptions before open questions. The order is: confirmed conflict, then orange doubts, then broken assumptions, then open questions, then confirmed.

`core/domain/status.py`, with 3.1 and 3.2 applied:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Status(str, Enum):
    CONFLICT = "CONFLICT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNCERTAIN = "UNCERTAIN"
    CONFIRMED = "CONFIRMED"


ORANGE_KINDS = frozenset({
    "SOURCE_CHANGED", "CONTEXT_CHANGED", "PROFILE_CHANGED", "EXPIRED",
    "AI_SUGGESTED", "POSSIBLE_CONFLICT", "SOURCE_OUTDATED",
})


@dataclass(frozen=True)
class PinFacts:
    origin: str                          # "HUMAN" | "AI_SUGGESTED"
    scope_type: str                      # "LAYER" | "CLIENT"
    confirmed_version_id: str | None
    latest_version_id: str               # latest ingested version of the pin's source (see 3.6)
    version_effective_to: datetime | None
    valid_until: datetime | None
    confirmed_profile_version: int | None
    client_profile_version: int | None   # None for layer pins
    passage_hash: str
    base: "PinFacts | None" = None       # set for exception pins
    base_passage_hash: str | None = None


def own_assumptions_hold(pin: PinFacts, now: datetime) -> bool:
    return (
        pin.origin == "HUMAN"
        and pin.confirmed_version_id == pin.latest_version_id
        and (pin.valid_until is None or pin.valid_until > now)
        and (pin.version_effective_to is None or pin.version_effective_to > now)
        and (
            pin.scope_type == "LAYER"
            or pin.confirmed_profile_version == pin.client_profile_version
        )
    )


def pin_status(pin: PinFacts, open_doubt_kinds: set[str], now: datetime) -> Status:
    if "CONFLICT" in open_doubt_kinds:
        return Status.CONFLICT
    if open_doubt_kinds & ORANGE_KINDS:
        return Status.NEEDS_REVIEW
    if not own_assumptions_hold(pin, now):
        return Status.NEEDS_REVIEW
    if pin.base is not None:
        if not own_assumptions_hold(pin.base, now):
            return Status.NEEDS_REVIEW
        if pin.base.passage_hash != pin.base_passage_hash:
            return Status.NEEDS_REVIEW
    if "QUESTION" in open_doubt_kinds:
        return Status.UNCERTAIN
    return Status.CONFIRMED
```

`passage_hash` is the SHA-256 of the whitespace-normalised prefix, quote and suffix joined with `\x1f`. It lives in `core/domain/passage.py` and is used by the status function, the seed and the re-anchoring engine alike.

### 3.3 Doubts cannot be assigned to a team

**Problem.** `Doubt.assigneeId` is required and points to a user, but fallback routing sends doubts to a team.

**Fix.** Add a `Team` model. `Doubt` gets a nullable `assignee_user` and a nullable `assignee_team`, with a check constraint that exactly one is set. A user's queue is their own doubts plus their team's doubts.

### 3.4 A consultant can supersede a layer pin

**Problem.** In the demo script (0:25 to 1:10), Lotte clicks "Supersede by" on the v1 procedure. That pin is a **layer** pin in *Belgium*. A consultant would be changing a verdict for every Belgian client, which is exactly the kind of business-logic flaw the Aikido audit looks for.

**Fix.**
- Consultants change verdicts only on client pins.
- On a layer pin, a consultant can only use "Ask" and "Source outdated".
- "Supersede by", "Confirm" and "Dismiss" on a layer pin are allowed only for the layer owner or the layer's team.

**Replacement for the demo script, 0:25 to 1:10:**

> Lotte opens Bakkerij Janssens → *correction deadline*:
> - Working instructions v3: 🟢 *Checked by Sarah P. against v3.* The 25th.
> - Correction deadline BE v1: 🟠 expired, no active owner, possible conflict with the Teams message *(AI, unverified)*.
> - Dutch procedure: under *Found but not applicable: scope NL*.
>
> Lotte answers the client from the green pin: the 25th. She clicks **Source outdated** on v1. The doubt goes to the Payroll BE team, because the owner left. Sarah P. (layer owner, Payroll BE team) then supersedes v1 by v3.

### 3.5 An AI conflict would turn the trusted pin orange

**Problem.** `compareClaims` will compare v1 ("the 20th") with v3 ("the 25th") and return `CONTRADICTS`. Under the spec, both pins get a `POSSIBLE_CONFLICT` doubt, so v3 turns 🟠 and the demo's green answer disappears. More generally, a stale, ownerless pin could downgrade every confirmed pin it disagrees with. That is the "false alarms erode trust" side effect the spec wants to avoid.

**Fix (proposed; see section 8).** Attach the `POSSIBLE_CONFLICT` doubt according to which pins currently hold their assumptions:
- If both pins hold their assumptions (both would be 🟢), both get a doubt.
- If exactly one holds, only the other pin gets a doubt, with the reason *"contradicts confirmed pin X"*.
- If neither holds, both get a doubt.

In the demo, v1 gets doubts for contradicting the Teams message and v3, while v3 stays 🟢. The Teams message must be seeded as a confirmed layer pin in *Belgium*, from a designated knowledge channel, so it can be compared at all.

### 3.6 "Current version" is undefined

**Problem.** If v2 of a source has a future effective date, the spec does not say whether v1 or v2 is current.

**Fix.** Pins must be confirmed against the **latest ingested** version (highest version number). Reviews therefore happen before a change takes effect, which is the point of prioritising by payroll close. The UI shows the effective range, for example *"v2 effective from 1 Jan 2027; v1 applies until then"*.

### 3.7 Doubts get duplicated

**Problem.** Re-running the expiry sweep or re-uploading a version creates duplicate doubts. A unique constraint on `(pin, related_pin, kind)` does not help, because SQL treats NULLs as distinct and `related_pin` is usually NULL.

**Fix.**
- `Doubt.dedupe_key` is a string built by code as `"{kind}:{pin_id}:{related_pin_id or ''}"`, and left NULL for `QUESTION` doubts (a pin can have several open questions).
- Add a conditional unique constraint on `dedupe_key` where `status = OPEN`. It works on both SQLite and Postgres.
- `SourceVersion.content_hash` with a unique constraint on `(source, content_hash)` rejects identical re-uploads.

### 3.8 Topics cannot be stored as a JSON array

**Problem.** SQLite does not support `contains` lookups on `JSONField`.

**Fix.** Add a `Topic` model. `Source.topics` becomes a many-to-many relation and `Pin.topic` a foreign key.

### 3.9 GCP credentials expire after one week

**Problem.** The hackathon's GCP credentials are valid for one week, and judging may happen later.

**Fix.**
- `AI_MODE=cache` is the repo default, not a nice-to-have.
- The cache key is a hash of task name, model name, prompt version and input. Otherwise an edited prompt silently serves stale output.
- A `gen_ai_cache` command runs the real model once on the seed data. The output is committed as `seed/ai-cache.json`.
- Before claiming EU data residency in the pitch, check that the chosen Gemini model is actually served in `europe-west1`.

### 3.10 A hosted deployment is not required

The participants guide asks for a description, a demo video under 3 minutes, a public repo and Aikido screenshots. It does not ask for a hosted URL.

**Fix.** Skip Cloud Run unless time is left over. Make the repo run offline from a fresh clone with SQLite, the seed and the AI cache, with no credentials. A judge who tries it will see it work.

---

## 4. Data model changes

Changes relative to `README.md` section 7. Everything not listed stays as specified, translated to Django models.

| Model | Change | Reason |
|---|---|---|
| `User` | Subclass `AbstractUser`; add `role` (CONSULTANT, OWNER, ADMIN) and `team` FK. Use Django's `is_active` instead of `active`. | Django auth |
| `Team` | New: `name` | 3.3 |
| `Layer` | `team` becomes an FK to `Team` | 3.3 |
| `Topic` | New: `slug`, `name` | 3.8 |
| `Source` | `topics` becomes M2M to `Topic` | 3.8 |
| `SourceVersion` | Add `content_hash`; unique on `(source, content_hash)` | 3.7 |
| `Pin` | `topic` becomes FK to `Topic`; add `passage_hash` (stored, recomputed on every move) and `base_passage_hash` (nullable) | 3.1, 3.8 |
| `Doubt` | Replace `assigneeId` with nullable `assignee_user` and `assignee_team`, plus a check constraint that exactly one is set; add `dedupe_key` with a conditional unique constraint where `status = OPEN` | 3.3, 3.7 |
| `AuditEvent` | Append-only: no update or delete path in code or admin | spec section 15 |
| `AiCache` | Key includes model name and prompt version | 3.9 |

---

## 5. Implementation plan

The critical path is **models → seed → status → views → resolve actions**. Everything else runs in parallel with it. Each step lists what must exist and how we know it is done.

### Step 0. Contract (30 minutes, whole team)

- Freeze the vocabulary from `README.md` section 1.
- Write `core/models.py` with [section 4](#4-data-model-changes) applied.
- Write `core/domain/status.py` as in 3.2.
- Update `README.md` sections 7, 11, 13, 14 and 15 to this stack and to fix 3.4.
- Name one migration owner. Nobody else edits `models.py` or creates migrations.
- The data person starts writing seed sources immediately; that needs no code.

**Done when:** the team agrees on the models and the status function.

### Step 1. Scaffold

- Django project `bron` with the single app `core`.
- Settings read from the environment. `DEBUG` defaults to `False`. `SECRET_KEY` is required. Session and CSRF cookies are `Secure` when not in debug, `HttpOnly` for the session, `SameSite=Lax`.
- Login and logout with Django's auth views.
- Base template with Tailwind and HTMX. The CSRF token is sent on every HTMX request through `hx-headers` on `<body>`.
- `pyproject.toml` (ruff, pytest), `requirements.txt`, `.gitignore` (including `.env` and `db.sqlite3`), `.env.example`.
- Push the repo publicly.

**Done when:** a seeded user logs in and sees an empty home page; `pytest` and `ruff check` pass.

### Step 2. Models, migrations and admin

- Implement the models; generate the initial migration.
- Register all models in the Django admin, which is restricted to the ADMIN role.

**Done when:** `migrate` runs from scratch on SQLite and every model is visible in the admin.

### Step 3. Seed

- `seed/sources/*.md`: one file per source version, with YAML front matter (id, title, type, owner, layer, scope, topics, version, effective dates, knowledge channel flag).
- `seed/seed.yaml`: teams, users, layers, clients, assignments and pins. Pins reference their passage by quote text only.
- `manage.py seed --reset` computes prefix, suffix and `passage_hash` from the content. If a quote does not occur exactly once in its version, the command fails loudly.
- The seed must match the demo script exactly, for example 9 pinned passages in the telework document so the ripple shows "8 unchanged, 1 modified". The Teams message is a confirmed layer pin (see 3.5).

**Done when:** running `seed` twice produces the same database, and every item in `README.md` section 10 exists.

### Step 4. Pure domain functions

- `domain/status.py` (3.1, 3.2).
- `domain/scope.py`: subscribed layers from each layer's scope rule and the client profile; the "found but not applicable" reason.
- `domain/effective.py`: the effective pins for a client and topic. Layer pins of subscribed layers plus client pins; exceptions shown on top of their base; superseded pins collapsed.
- `domain/templates.py`: the explanation lines from `README.md` section 4.8.
- `domain/passage.py`: normalisation and `passage_hash`.
- No ORM imports anywhere in `domain/`.

**Tests:** a status truth table covering every doubt kind, every broken assumption and the exception cases; scope matching; the effective set.

**Done when:** the tests pass.

### Step 5. Authorization and read views

- `core/authz.py`: `can_read_client`, `can_read_pin`, `can_resolve_doubt`, `can_change_layer_pin`, `can_upload_version`, and queryset helpers such as `clients_for(user)`.
- Inaccessible IDs return 404, not 403, so existence is not leaked.
- Views: home (my clients and my queue), client file, topic detail, doubt detail, and a question view for experts that shows only the question and the passage.

**Tests:** Pieter gets 404 on Bakkerij Janssens; a consultant cannot see other clients' doubts; an expert receiving a question cannot open the client file.

**Done when:** story 1 renders read-only with the correct statuses and reasons.

### Step 6. Resolve actions (skateboard)

- `services/actions.py`, one function per action: confirm, supersede, does not apply, add exception, escalate, dismiss, ask, source outdated.
- Each function checks authorization, enforces the rules from `README.md` section 4.6 and fix 3.4, runs in `transaction.atomic`, and writes an audit event.
- Views accept HTMX POSTs validated by Django forms.

**Tests:** one per rule. Confirm only against the latest version. Dismiss only for the allowed doubt kinds. Escalate only from a possible conflict. A consultant cannot change a layer pin's verdict. The AI and the system user cannot resolve anything.

**Done when:** story 1 works end to end. **Run the Aikido baseline scan and take the "before" screenshot.**

### Step 7. Re-anchoring and sensitive-change detection

- `engine/reanchor.py`, as in `README.md` section 4.4: exact match, context changed, ambiguous, fuzzy match (similarity ≥ 0.75) as modified, and deleted.
- `engine/sensitive.py`: extract numbers, percentages, amounts and dates from the old and new text; any difference means severity 1.

**Tests:** one per outcome, including a moved passage and a changed suffix such as an added "except for PC 124".

**Done when:** the tests pass on the real telework v1 and v2 seed files.

### Step 8. Invalidation engine and ripple (bicycle)

- `engine/invalidate.py`: events to doubts, using `dedupe_key`.
- `engine/route.py`: assignee, fallback team when the owner is inactive, and due date (a client's next payroll close; for a layer, the earliest next payroll close among subscribed clients on or after the version's effective date).
- `services/ripple.py`: upload, re-anchor, auto-carry unchanged passages with an audit event, create doubts, controlled fan-out.
- An upload view that shows the ripple summary. A `sweep` management command for expiry. Profile-change invalidation when a client profile is edited.

**Tests:** a layer change creates exactly one layer doubt plus one per dependent exception, and none for clients that only inherit; the fallback team is used when the owner is inactive; running the ripple twice creates no duplicates.

**Done when:** the demo ripple runs on the real v1 and v2 files. **Fix the Aikido findings.**

### Step 9. AI (motorcycle)

- `ai/client.py` (google-genai, temperature 0, JSON output), `ai/schemas.py` (pydantic), `ai/tasks.py` (`extract_claims`, `compare_claims`, `triage_change`), `ai/cache.py`, `ai/prompts/`.
- Source text is passed inside a delimited data block, with the instruction to treat it as content only. The model has no tools.
- The quote check discards any claim whose quote does not occur literally in the passage.
- Conflict doubts follow the attachment rule in 3.5.
- A `gen_ai_cache` command runs the real model once. Commit `seed/ai-cache.json`.

**Tests:** an invented quote is discarded; invalid model output produces a doubt without an AI label; a fresh clone in cache mode needs no GCP access.

**Done when:** a fresh clone, seeded in cache mode, shows AI labels without credentials.

### Step 10. UI polish

Status badges, collapsed superseded pins, "pending with" lines, the grey *AI (unverified)* styling, and the ripple summary screen.

### Step 11. Freeze (last 20% of the time)

- Final Aikido scan and the "after" screenshot, stored in `docs/aikido/`.
- Update the README's "what's unfinished" section.
- Record the demo video and submit through Builderbase.

---

## 6. Project structure

```
bron/
  manage.py
  requirements.txt
  pyproject.toml              ruff and pytest configuration
  .env.example
  bron/                       settings.py, urls.py, wsgi.py
  core/
    models.py
    admin.py
    authz.py                  every access check lives here
    audit.py
    forms.py
    urls.py
    domain/                   pure functions, no ORM imports
      status.py
      scope.py
      effective.py
      templates.py
      passage.py
    engine/
      reanchor.py
      sensitive.py
      invalidate.py
      route.py
    services/
      actions.py              resolve actions, one function each
      ripple.py               upload → re-anchor → carry → doubts
    ai/
      client.py
      schemas.py
      tasks.py
      cache.py
      prompts/
    views/
    templates/core/
    management/commands/
      seed.py
      sweep.py
      gen_ai_cache.py
  seed/
    sources/*.md
    seed.yaml
    ai-cache.json             real model output, for offline runs
  tests/
  docs/
    decisions.md
    aikido/                   before and after screenshots
```

---

## 7. Cut order, team split, Aikido timing

**Cut order if time runs short** (first cut first):
1. Cold-start AI suggestions.
2. Profile-change invalidation.
3. The `sweep` command. Expiry is still shown at read time without it.
4. AI triage labels.

Never cut steps 1 to 8. They are the product.

**Team split after step 2:**

| Role | Steps | Name |
|---|---|---|
| Backend and security | 5, 6 | |
| Engine and AI | 4, 7, 8, 9 | |
| Frontend | Templates from step 3 onward, then 10 | |
| Data and pitch | 3, mentor questions, demo script, video, README | |

**Aikido:** baseline scan after step 6, fixes after step 8, final scan at freeze.

---

## 8. Review requests

Second opinion requested on these points before implementation:

1. Is Django + HTMX the right choice over Next.js for this spec, given one day and a security criterion?
2. Are fixes 3.1 to 3.10 correct and complete? Especially:
   - 3.1: does the exception dependency cover every way a base pin can change?
   - 3.5: is the asymmetric conflict attachment safe, or can it hide a real conflict between a confirmed pin and a stale one that later gets re-confirmed?
   - 3.6: is "latest ingested version" the right definition of current?
3. Is there any path through `pin_status` that returns 🟢 when an assumption is broken?
4. Is any route in `README.md` section 8 still exploitable through IDOR or business logic, after fix 3.4?
5. Is the critical path in section 5 realistic for a four-person team in one day, and is the cut order right?

---

## 9. Target run commands

These must work from a fresh clone, offline, with no credentials:

```bash
git clone <repo-url>
cd bron
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set DJANGO_SECRET_KEY; never commit .env
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Demo logins are listed in `seed/README.md` (synthetic accounts only).
