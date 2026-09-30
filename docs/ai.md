# Structured evidence checks

There are three provider tasks: `extract_claims`, `compare_claims`, and `triage_change`. Pydantic rejects extra fields and invalid enums. Quotes must occur literally in their supplied passage. The model sees a JSON source-data block under a separate system instruction, has no tools, and cannot call an application action.

The checked-in cache is **synthetic, hand-authored test data**, not Gemini output. The UI labels that provenance. Cache misses do not call the cloud in cache mode. They leave the existing deterministic status and review engine intact. Invalid outputs create a doubt without an AI label.

Conflicts are considered only within overlapping country/client/topic scope. If both passages hold their assumptions, both get a possible-conflict doubt. If one holds, only the other gets a doubt; if neither holds, both do. Dedupe keys prevent repeated comparisons from duplicating open doubts. A possible conflict needs a human dismissal, escalation or supersession before confirmation; AI cannot clear it.

`build_demo_ai_cache` regenerates labelled test fixtures on a fresh demo database. `gen_ai_cache` runs the real configured Vertex provider against those same inputs, then writes the file only if all tasks succeed. Existing cached results can be reused for the same model/prompt/input. No cloud credentials are checked in.

Production AI decisions must also respect organisational data policy, quota, IAM and regional model availability. No claim of EU-only inference is made by this application merely because `GCP_LOCATION` defaults to `europe-west1`.
