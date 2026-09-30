# Fake knowledge corpus

Test data for our SD Worx hackathon prototype. **Everything here is fictional**: people, clients, systems, procedures and dates. No real SD Worx data is used.

The demo date is **30 September 2026**. Judge "outdated" and "recent" against that date.

## Contents

```
data/
├── documents/        10 documents, Markdown with YAML metadata
├── teams/            1 Teams thread, JSON
├── people.json       people directory, used for owners and "who to ask"
└── eval_questions.json   8 test questions with expected answers
```

## Metadata fields

Every document and the Teams thread has these fields:

| Field | Meaning |
|---|---|
| `id` | Unique source ID |
| `title` | Title of the source |
| `type` | procedure, checklist, calendar, guide, client_file or teams_thread |
| `source` | Where it lives (fictional SharePoint, shared drive, mysdworx or Teams path) |
| `owner` | Person ID from `people.json`, or `null` if nobody owns it |
| `last_updated` | Date of the last edit |
| `country` | BE, NL or LU |
| `client` | `all`, a client ID, or `null` if unknown |
| `status` | approved, unknown |
| `version` | Version number, or `null` |

Chats have no owner and no client tag. The tool has to work out from the messages which client they're about.

## Planted conflicts

This section is a spoiler for testing.

- **Stale document.** `BE-PAY-CHK-2022` says the input deadline is the 3rd working day. It has no owner and dates from 2022. The official procedure `BE-PAY-PROC-001` says the 5th, and its change log explains the switch.
- **Wrong country.** `NL-PAY-PROC-001` gives a different deadline, which is correct but only for the Netherlands.
- **Undocumented exception.** In the Teams thread, Brouwerij De Kroon gets the 7th working day until end of 2026. The client file still says "no deviations recorded", and the procedure says unrecorded exceptions aren't valid. The answer only lives in chat.
- **Scope limit.** The same thread says the exception does *not* apply to Garage Verhaeghe.
- **Owner who left.** `BE-HANDOVER-2019` belongs to Marc Peeters, who left in 2024. The 2026 checklist replaces it, but doesn't say so explicitly.
- **Knowledge gap.** Nothing covers Luxembourg. The right answer is "not found, ask Anne Muller".
- **Controls.** The payslip and expense questions have no conflicts. The tool shouldn't invent one.

## Using the eval questions

Run each question in `eval_questions.json` through the tool and compare the result with `expected_answer`, `trusted_sources`, `sources_to_flag` and `who_to_ask`. Q1 and Q2 are the main demo questions.
