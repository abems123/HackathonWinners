# Bron — codebase handoff for Claude or another implementing agent

This is the technical continuation guide. Start here, then read [README.md](README.md) for the product and demo. The repository is `https://github.com/abems123/HackathonWinners.git`, branch `main`.

## What the user asked for

Build the complete website from the repository README, work step by step with checks between stages, commit the finished work, and push to the connected GitHub repository. The user subsequently asked for **a commit and push after each implemented, verified feature** and this continuation README.

The original repository README was an implementation plan, not the product specification it referenced. It is preserved verbatim in [docs/implementation-plan.md](docs/implementation-plan.md). Some of its references to sections 10/15 of a product spec cannot be resolved. Conservative assumptions are recorded in [docs/decisions.md](docs/decisions.md); do not pretend the absent spec was implemented verbatim.

The teammate added a fictional corpus and later a Render deployment commit while this implementation was running. Preserve that work. This is a shared checkout: inspect `git status` and recent commits before editing. Never overwrite another contributor's uncommitted files or force-push.

## Product in one paragraph

Bron is a payroll knowledge workspace. A consultant chooses a client and a controlled topic. The app assembles relevant shared-layer passages and private client passages, puts client exceptions above their base rule, and shows derived trust status. A source version, profile or expiry change can reopen reviews. Humans confirm or resolve; structured AI can only suggest or flag. There is no chatbot or free-text search.

## Stack and startup

- Python 3.11/3.12, Django 5.2 LTS, one Django app: `core`.
- SQLite for local demos; PostgreSQL via `DATABASE_URL` and psycopg.
- Server-rendered Django templates, local HTMX 2.0.8, Tailwind 3.4.17 compiled with a standalone executable, plus custom CSS.
- WhiteNoise with compressed, hashed production assets. Render terminates HTTPS; its proxy headers are recognised only when `RENDER=true`.
- rapidfuzz for conservative fuzzy passage matching; Pydantic for model output schemas; google-genai for Vertex AI.
- Markdown rendering is sanitised with bleach before it is marked safe.

Windows commands from repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
Copy-Item .env.example .env
# Set a long random DJANGO_SECRET_KEY in .env; keep DJANGO_DEBUG=True locally.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py runserver
```

On Linux/macOS use `.venv/bin/python` and `cp`. Open `http://127.0.0.1:8000`. Demo password is `Bron-demo-2026!`; usernames include `lotte`, `sarah`, `sofie`, `pieter`, `anne`, and `admin`. The `system` account has an unusable password. Seed accounts are exclusively for synthetic demonstrations.

If login "does nothing" or the browser jumps to `https://127.0.0.1`, the server is running with `DJANGO_DEBUG=False` over plain HTTP: keep `DJANGO_DEBUG=True` locally, or set `DJANGO_HTTPS=False` when deliberately testing a non-debug build over HTTP. A missing `DJANGO_SECRET_KEY` now fails with an explicit message. Always install from `requirements.lock` (it now contains Markdown, bleach, gunicorn and psycopg; their absence was why tests failed).

`.env`, SQLite databases, the virtual environment, compiled Tailwind executable and `output/` are ignored. Do not read, print or commit credentials. `DJANGO_SECRET_KEY` is required; debug defaults to false. Model name and cloud project are environment configuration, not hard-coded.

## File map

| Area | Main files | Responsibility |
| --- | --- | --- |
| Django configuration | `bron/settings.py`, `bron/urls.py`, `bron/wsgi.py` | Security, database, static assets, auth routes and Render integration |
| Test configuration | `bron/test_settings.py` | In-memory DB, test-only fast password hashing, non-manifest test asset storage |
| Data model | `core/models.py`, `core/migrations/` | Users, teams, clients, layers, topics, sources/versions, pins, doubts, audit events and AI cache |
| Pure domain | `core/domain/status.py`, `passage.py`, `scope.py`, `effective.py`, `templates.py` | Derived status, anchors/hashes, matching, effective pin set and fact-based explanations; no ORM imports |
| Permissions | `core/authz.py` | Central per-resource read/change/upload/resolve checks and visible querysets |
| Review actions | `core/services/actions.py`, `core/forms.py` | Transactional human actions and input validation |
| Change engine | `core/engine/reanchor.py`, `sensitive.py`, `invalidate.py`, `route.py` | Conservative match outcomes, changed values, dedupe and ownership/due-date routing |
| Source updates | `core/services/ripple.py` | Version upload, unchanged carry, modified passage review, exception fan-out and expiry sweep |
| AI provider | `core/ai/client.py`, `schemas.py`, `tasks.py`, `cache.py`, `prompts/` | Structured calls, literal quote checks, cache keys and provenance |
| AI review | `core/services/ai_review.py` | Compare only overlapping topic/scope; attach possible-conflict doubts, never verdicts |
| Routes/screens | `core/urls.py`, `core/views.py`, `core/templates/core/` | Portfolio, client/topic, pin review, doubt/question, source/upload/ripple, people, activity |
| Frontend | `core/static/core/app.css`, `app.js`, `tailwind.css`, `vendor/` | Responsive UI, small menu/action interactions and offline assets |
| Template helpers | `core/templatetags/bron_tags.py` | Developer-owned SVG icons and sanitised Markdown rendering |
| Seeds | `core/management/commands/seed.py`, `seed/seed.yaml`, `seed/sources/` | Idempotent synthetic users/clients/pins and telework update fixture |
| Teammate corpus | `data/documents/`, `data/teams/`, `data/people.json`, `data/eval_questions.json` | Original fictional documents, ownership directory and expected evaluation scenarios |
| Checks | `tests/`, `tools/browser_smoke.py`, `tools/verify_browser.py`, `.github/workflows/checks.yml` | Domain/service/security/corpus regression and isolated real-browser verification |
| Deployment | `render.yaml`, `build.sh`, `start.sh`, `docs/deployment.md` | Teammate's Render configuration; do not assume a live deployment was verified |

## Data relationships and invariants

`User` extends Django `AbstractUser` with `role` and optional `team`. Roles are CONSULTANT, OWNER, ADMIN, EXPERT and SYSTEM. `Client.consultants` is the private-client assignment relation. `Layer` has a scope-rule dictionary, owner and responsible team. `Topic` is a real table, because SQLite cannot perform JSON-array containment as required by the plan.

`Source` belongs to exactly one layer or client, has many topics, and keeps original corpus metadata/external ID. `SourceVersion` is immutable: highest ingestion `number` is latest, while `label` preserves corpus labels such as 4.2. Content hash and version number are unique per source. Effective dates are separate from ingestion order.

`Pin` references a source version, exact quote and paragraph-local prefix/suffix. `passage_hash` is SHA-256 of whitespace-normalised prefix/quote/suffix joined by `\x1f`. A pin belongs to one layer or client. A client exception references a layer `base` and the base passage hash that was reviewed. Confirmation records person/time/source version and client profile version. `superseded_by` and `excluded` control active applicability.

**There is no stored status column.** `Pin.status` constructs `PinFacts` and invokes the pure domain function. Priority is confirmed conflict, orange doubts, broken assumptions, base dependency failure, question, then confirmed. Origin must be human, confirmed version must match latest ingestion, expiry/effective end must still hold, and the client profile version must match. A missing confirmation is never green. A base's own status, hash, exclusion and supersession also invalidate an exception.

`Doubt` has exactly one user or team assignee. Open non-question doubts use `KIND:PIN_ID:RELATED_PIN_ID_OR_EMPTY` as `dedupe_key`, protected by a conditional unique constraint. Questions may coexist and use no dedupe key. `AuditEvent` is append-only through model/queryset/admin paths; actual database administrators can still alter a database, so external archival is a separate operational concern.

## Read and write flows

### Client/topic lookup

1. `views.get_client` checks `authz.can_read_client`; inaccessible/malformed IDs return 404.
2. `authz.pins_for` restricts private client passages while permitting shared-layer knowledge.
3. `domain.effective.effective_pins` selects matching layers and that client's pins, returns out-of-scope and superseded groups, and sorts exceptions first.
4. Templates show quotes, derived statuses, deterministic explanations and effective dates. Luxembourg intentionally has no grounded payroll answer and refers to Anne Muller.

Layer reading is organisation-wide for consultants/owners/admins so wrong-country sources can be explained as outside scope. Client reading needs assignment, admin privileges or oversight of a subscribed layer. An OWNER role alone does not grant all client access.

### Human decisions

Every action POST goes through `ActionForm` and `services.actions.perform` inside a transaction. Mutations also repeat the authorisation check. The service records an audit event after the decision.

- Consultants can change client pins; on layer pins they can ask or flag source outdated.
- Layer verdicts require OWNER/ADMIN and the responsible owner/team scope.
- Confirm checks the latest version ID, exact unique quote, active status, expiry, unresolved questions/conflicts and base trust. It is not an implicit conflict dismissal.
- Supersede requires a confirmed active replacement in the same topic and scope.
- General dismissal is limited to QUESTION, AI_SUGGESTED, POSSIBLE_CONFLICT and SOURCE_OUTDATED, with a reason.
- Escalation requires a possible-conflict doubt and creates a human-confirmed CONFLICT doubt.
- New exceptions initially need review; creating an agreement does not confirm it.
- Assigned humans can answer a question; expert question access does not grant client/source access. Expert dashboard/queue entries hide client/source labels.
- SYSTEM/AI have no confirmation or resolution path. The admin is deliberately read-only for domain objects so it cannot bypass audited services.

All source IDs, pin IDs, doubt IDs and client IDs must be checked through `core/authz.py`. Return 404 for inaccessible objects. Keep CSRF and POST-only mutation enforcement.

### Source ripple

`upload_version` locks the source, rejects duplicate content, and ingests one immutable version. Matching yields UNCHANGED, CONTEXT_CHANGED, AMBIGUOUS, MODIFIED (fuzzy similarity >= 0.75), or DELETED. Only unchanged passages with a prior human confirmation can carry that confirmation. Changed/missing/ambiguous passages reopen; dependent client exceptions get their own review. Ordinary clients inheriting a shared layer do not get duplicate doubts.

Sensitive numbers/amounts/percentages/dates raise deterministic priority. AI triage may add an unverified label but cannot reduce deterministic severity. Routing prefers active source owners and otherwise the responsible team; due dates use the next applicable client payroll close. Latest ingestion is the review target even when its effective date is in the future.

The telework fixture is deliberate: v1 contains nine pinned paragraphs. Uploading `seed/sources/telework-v2.md` produces **8 unchanged, 1 modified, 1 dependent exception**. It is not pre-ingested by the seed. Repeat uploads and expiry sweeps create no duplicate open doubts.

### Structured AI

Three tasks: extract claims, compare claims and triage changes. Inputs are untrusted source data, passed under a separate system instruction; the provider has no tools. Pydantic validates output. Claimed quotes must occur literally in their corresponding input. Missing/invalid evidence never creates false confirmation; invalid results create manual review without an AI label.

`AI_MODE=cache` is the default. `seed/ai-cache.json` is **synthetic hand-authored fixture data, not Gemini output**. The UI labels it accordingly. The key contains task, model, prompt content version and input. Cache misses never call the cloud in cache mode.

Possible conflicts are attached asymmetrically: both pins if both/neither hold assumptions, otherwise only the stale pin. A confirmed current Belgian procedure stays green when a stale checklist disagrees. Client exceptions never spread to another client or country. Explanation/reason lines are code templates filled with facts, not LLM explanations.

`build_demo_ai_cache` regenerates synthetic fixtures only in debug mode. `gen_ai_cache` requires real Vertex configuration and ADC; it writes the checked-in cache only after all tasks succeed. Keep `GEMINI_MODEL` set to the generated cache's model when returning to cache mode. Live provider code exists, but actual cloud credentials were not available for validation. See [docs/ai.md](docs/ai.md).

## Checks to run before each feature push

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
git diff --check
```

For UI/source/review changes:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
.\.venv\Scripts\python.exe tools/verify_browser.py
```

The wrapper creates a separate temporary SQLite database and server, runs seven real Chrome workflows, then removes only that temporary test state. It does not reset the developer's demo database. Chrome must be installed; alternatively install Playwright Chromium and set `BRON_BROWSER_CHANNEL=chromium`. Screenshots/report are in ignored `output/browser/`. Inspect desktop and mobile screenshots as well as assertions; wait for responsive menu transitions before capturing.

The test suite covers CSRF-enforced login, CRLF uploads (browser textareas/Windows files must still give 8/1/1), the status truth table, exception dependencies, repeated seed/ripple/sweep, object permissions and CSRF, all review rules, audit protections, structured output failures, scope isolation and all **eight** teammate corpus evaluation questions. Test-only password hashing is intentionally fast; do not copy it into production settings.

The original connected browser runtime could not start because its Windows sandbox helper failed. Headless Playwright/Chrome testing succeeded as a repository test fallback; do not report that no browser verification happened.

## Commands and operational cautions

- `seed` is idempotent and preserves reviews; `seed --reset` flushes the entire demonstration database and is debug-only. Never run reset against a shared database merely to make tests pass.
- `sweep` creates deduplicated expiry reviews. Status also checks expiry at read time even without a sweep.
- `tools/build_css.ps1` downloads the pinned Windows Tailwind standalone compiler and rebuilds the checked-in CSS. Runtime needs no Node/CDN.
- `build.sh` installs `requirements.lock` and collects static assets; `start.sh` applies migrations, runs the idempotent demo `seed` when `BRON_SEED_DEMO=true` (set in `render.yaml`, so the deployed login accounts exist) and starts Gunicorn. Set it to `false` before real data is stored. Review Render's database/host/CSRF variables in `docs/deployment.md` before deploying.
- Demo dates are around 30 September 2026; payroll closes are October 2026. The real clock controls expiry, so time-dependent demo states can change later. Do not freeze production time to keep badges green.
- Several teammates/agents have committed during implementation. Always inspect status and preserve unrelated files such as a deployment patch. Use explicit `git add` paths. Normal fast-forward pushes only.

## What remains external or intentionally bounded

- Real Vertex inference and a genuinely generated cache require team cloud credentials. Do not claim the synthetic fixtures are model output.
- Aikido before/after screenshots require the team's Aikido account. No fake screenshots/results were generated.
- Demo recording and Builderbase submission are team deliverables; this codebase does not claim those happened.
- Render configuration is present; local checks do not establish that a hosted deployment is healthy.
- Source re-anchoring is conservative paragraph matching, not a general legal document parser. Ambiguous cases must stay in review.
- The admin intentionally offers inspection rather than unaudited CRUD. Expand the application's workflow through authorised, validated services if new creation/edit screens are requested.

Before continuing, read the current `git log` and run the relevant checks. The code and migrations, not the historical plan's proposed status, are the source of truth for what exists. Update this handoff when behaviour changes, then commit and push the verified feature as the user requested.
