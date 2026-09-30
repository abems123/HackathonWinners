# Synthetic demonstration

Run `python manage.py seed`. Repeat runs preserve existing reviews. `--reset` replaces the entire demo database and is restricted to debug mode.

All active demo accounts use `Bron-demo-2026!`. Use `lotte` for a consultant, `sarah` for a layer owner, `sofie` for the corpus owner, `pieter` for De Kroon's consultant, `anne` for the restricted expert, or `admin` for read-only administration. Never load demo accounts into a production database.

The original teammate corpus is in `data/` and is imported unchanged, including its version labels. Integer ingestion versions are separate from those labels. Additional correction and telework scenarios fulfil the implementation plan. `telework-v2.md` is an upload fixture; it is deliberately not ingested during seed. Its expected ripple is 8 unchanged, 1 modified, and 1 dependent client exception reopened.

All dates are fictional. Demo payroll closes are October 2026. The app uses the actual clock for expiry; it does not freeze production time to keep demo pins green.
