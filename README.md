# Bron — knowledge you can stand behind

Bron brings shared procedures, client context and human review into one workspace. Select a client and a topic to see source-backed passages, their current trust status, and the person responsible for resolving uncertainty.

For Claude or another developer continuing this project, read [README_CLAUDE.md](README_CLAUDE.md) for the architecture, file map, invariants and verification workflow.

**All people, clients, documents and dates in the demonstration are fictional. No real SD Worx data is used.**

## Run locally

Requires Python 3.11 or 3.12. SQLite is included in Python.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Replace DJANGO_SECRET_KEY in .env with a long random value.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed
.\.venv\Scripts\python.exe manage.py runserver
```

On macOS/Linux use `.venv/bin/python` and `cp .env.example .env` instead. Open http://127.0.0.1:8000.

Sign in as `lotte` (consultant), `sarah` (layer owner), `sofie` (corpus owner), `pieter` (De Kroon consultant), `anne` (restricted expert), or `admin` (administration). Demo password: `Bron-demo-2026!`. Full details: [seed/README.md](seed/README.md).

Once dependencies are installed, the synthetic demo works offline with no cloud credentials. Styles and HTMX are checked in and served locally.

## Implemented

- Django sessions, login/logout, CSRF protection, object access checks and immutable source versions.
- Client portfolio, topic browsing, shared layers, private client exceptions and out-of-scope results.
- Derived trust status: confirmed, needs review, open question, conflict. Broken assumptions always trigger review.
- Review actions: confirm, supersede, mark not applicable, add exception, escalate, dismiss, ask, source outdated and expert answer.
- Named/team review queues, due-date routing, inactive-owner fallback and append-only application audit events.
- New-version upload with exact/context/fuzzy/ambiguous/deleted passage detection, sensitive-value prioritisation, unchanged passage carry and exception invalidation.
- Profile invalidation and deduplicated expiry sweeps.
- Import of the teammate's 10-document corpus and Teams thread, plus correction and telework demonstrations.
- Responsive, accessible server-rendered interface with local HTMX and compiled Tailwind styles.

## Demo workflows

1. **Payroll input:** as Lotte, open Bakkerij Janssens → Payroll input. The current Belgian procedure is confirmed; the old checklist needs review; the Dutch rule appears outside scope.
2. **Unrecorded exception:** open Brouwerij De Kroon → Payroll input. The temporary 7th-working-day exception is visible above its base and requires human confirmation. Other clients do not inherit it.
3. **Knowledge gap:** Maison Laurent → Payroll input has no applicable answer and points to Anne Muller.
4. **Corrections:** Lotte flags the outdated correction procedure; Sarah supersedes it with working instructions v3.
5. **Ripple:** as Sarah, Sources → Telework allowance · PC 200 → Upload new version. Upload `seed/sources/telework-v2.md`, effective 1 January 2027. The result is 8 unchanged, 1 modified and 1 dependent exception reopened. Re-uploading creates no duplicates.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
git diff --check
```

Tests use isolated in-memory SQLite and fast test-only password hashing. Normal accounts use Django's production password hasher.

`requirements.lock` records the verified package versions. For browser verification, install `requirements-browser.txt`, then run `python tools/verify_browser.py`. This starts a separate temporary database and server, exercises seven Chrome workflows, and writes screenshots and a report to `output/browser/` without changing your working demo. Chrome must be installed; alternatively run `python -m playwright install chromium` and set `BRON_BROWSER_CHANNEL=chromium`.

The eight questions in `data/eval_questions.json` have semantic regression checks in `tests/test_corpus_eval.py`. GitHub Actions runs the suite and browser checks on each push.

## Operations

`python manage.py seed` is repeatable and preserves decisions. `python manage.py seed --reset` replaces the demo database; it is allowed only in debug mode. `python manage.py sweep` generates deduplicated expiry reviews. The actual clock determines status; demo dates are not frozen.

Production defaults to `DJANGO_DEBUG=False`, secure cookies, HTTPS redirection and HSTS. Set `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and optionally `DATABASE_URL` for PostgreSQL, and run `collectstatic`. Never deploy seeded demo passwords or commit `.env`, a database, or cloud credentials. Database-level immutable archival is separate from the application's append-only audit protections.

To rebuild styles on Windows, run `tools/build_css.ps1`; it downloads Tailwind's pinned standalone compiler. Normal startup needs no CSS build or Node toolchain.

## Design and remaining external work

The original repository contained an implementation plan referencing a missing product specification. It is preserved in [docs/implementation-plan.md](docs/implementation-plan.md). Conservative gap-filling decisions are in [docs/decisions.md](docs/decisions.md). Render deployment instructions are in [docs/deployment.md](docs/deployment.md).

Structured Vertex AI integration is implemented with three validated tasks: extract claims, compare claims and triage changes. Source owners can use **Check evidence** on a source. Cache mode uses explicitly labelled synthetic fixtures, works offline, and never invents model provenance. Quote validation rejects hallucinated evidence. Invalid results create a manual review without an AI label.

To generate real cached results, configure Application Default Credentials, set `AI_MODE=live`, `GCP_PROJECT`, `GCP_LOCATION` and `GEMINI_MODEL`, then run `python manage.py gen_ai_cache`. Cache keys include task, model, prompt content version and input. Keep `GEMINI_MODEL` set to the same model when serving those results in cache mode. The live provider has no tools and cannot confirm or resolve anything.

Real model cache generation, Aikido before/after screenshots and demo-video submission require the team's external accounts. No completed external scan or model provenance is claimed.
