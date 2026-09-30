# Bron: website overview and video guide

Live: https://hackathon-winners.onrender.com (visitors are signed in automatically as Lotte)
All people, clients, documents and dates are fictional. No real SD Worx data is used.

---

## 1. One-line pitch

**Bron is a payroll knowledge workspace that shows a consultant which rule applies to a client and whether that rule can still be trusted.**

## 2. The problem

Payroll consultants work from many overlapping sources: country procedures, sector rules
(joint committees such as PC 200), old checklists, client-specific agreements and Teams threads.
- Sources contradict each other (e.g. a checklist says the 3rd working day, the procedure says the 5th).
- Client exceptions are hidden in emails or someone's head.
- When a source changes (e.g. a new telework allowance amount), nobody knows which answers
  are now wrong or which clients are affected.
- Chatbots give confident answers without saying whether anyone checked them.

## 3. The solution: what Bron does

1. **Pick a client, pick a topic.** Bron shows only the passages that apply to that client
   (country, joint committee), with the exact quoted source text.
2. **Every passage has a trust status**, derived automatically:
   - Confirmed: a named person checked it against the latest version of the source.
   - Needs review: the source changed, expired, or something conflicts.
   - Open question: someone asked; an expert is assigned.
   - Conflict: a person confirmed that two sources disagree.
3. **Client exceptions sit above the base rule.** If the base rule changes, the exception is
   reopened too. Exceptions never leak to other clients.
4. **Out of scope is explained.** A Dutch rule shows up as "found but not applicable" for a Belgian client.
5. **Knowledge gaps are honest.** If there is no answer, Bron says so and names the expert to ask.
6. **Change ripple.** When a source owner uploads a new version, Bron compares it passage by
   passage: unchanged passages keep their confirmation, changed ones go to the right owner's
   review queue with a due date before the next payroll close.
7. **Humans decide, AI only suggests.** The AI evidence check can flag a possible conflict,
   but it can never confirm or resolve anything. Every decision needs a reason and goes into
   an append-only audit log.
8. **No chatbot, no free-text search.** You navigate by client and topic, so you cannot get
   an ungrounded answer.

## 4. Roles (demo accounts, password `Bron-demo-2026!`)

| User   | Role                 | What they do in the demo                          |
|--------|----------------------|---------------------------------------------------|
| lotte  | Consultant           | Reads client knowledge, asks questions, flags outdated sources |
| sarah  | Layer owner (BE)     | Confirms/supersedes shared rules, uploads new source versions |
| pieter | Consultant De Kroon  | Second consultant on Brouwerij De Kroon           |
| anne   | Expert (Luxembourg)  | Answers questions without seeing client data      |
| admin  | Administrator        | Read-only inspection                              |

The site signs you in as **lotte** automatically. To switch to **sarah**: click the sign-out
icon (bottom left), then sign in on the login page as `sarah`.

## 5. Video script (about 3 minutes)

**0:00 Intro (problem).** "Payroll consultants juggle procedures, checklists and client
exceptions. When one source changes, nobody knows which answers are now wrong. Meet Bron."

**0:20 Scene 1: Overview (as Lotte).** Show the dashboard: her clients, how many passages are
confirmed and how many need review, and the review queue.

**0:40 Scene 2: Bakkerij Janssens → Payroll input.**
- The Belgian procedure (5th working day) is **Confirmed**, with who checked it and against which version.
- The old closing checklist (3rd working day) shows **Needs review**: possible conflict, source outdated.
- Open "Found but not applicable": the Dutch procedure is shown as **outside scope** (country NL, client BE).
- Say: "Bron doesn't hide the contradiction; it shows it, and who has to fix it."

**1:10 Scene 3: Brouwerij De Kroon → Payroll input.**
- The client exception (temporary 7th working day) appears **above** the base rule and needs human confirmation.
- Say: "Other clients do not inherit this exception."

**1:30 Scene 4: Maison Laurent (Luxembourg) → Payroll input.**
- No grounded answer. Bron says so and points to the expert, Anne Muller.
- Say: "No answer is better than a wrong answer."

**1:45 Scene 5: The ripple (as Sarah).**
- Sign out, sign in as `sarah`. Go to Sources → *Telework allowance · PC 200* → **Upload new version**.
- Upload `seed/sources/telework-v2.md` from the repo, effective 1 January 2027.
- Result: **8 unchanged, 1 modified (EUR 148.73 → EUR 154.20), 1 client exception reopened.**
- Say: "One change, clear impact. Only the passage that changed needs a person again."

**2:20 Scene 6: Human in the loop.**
- Open a passage → Review passage: show actions (confirm, supersede, ask, flag outdated), all requiring a reason.
- Optionally, still as Sarah: Sources → a source → **Check evidence** (structured AI check that
  can only flag possible conflicts; available to source owners).
- Show the **Activity log** (audit trail).

**2:45 Close.** "Bron: grounded in sources, confirmed by people. Knowledge you can stand behind."

### Recording tips
- The ripple upload works **once** per database. A second upload of the same file shows
  "duplicate" and changes nothing. Rehearse locally first, then record on the live site.
- Actions such as confirm/supersede change the shared demo data for everyone. Record them last.
- The free Render server sleeps when idle: open the site 1 minute before recording.

## 6. Technology (for a tech slide)

- Django 5.2 (Python), PostgreSQL on Render, server-rendered templates with HTMX and Tailwind
  (no JavaScript framework, no CDN, works offline).
- Trust status is **never stored**: it is computed from facts (who confirmed which version,
  expiry, open doubts, client profile), so it cannot silently go stale.
- Passages are anchored by exact quote + surrounding context + SHA-256 hash; new versions are
  matched exactly first, then fuzzy (≥ 75% similarity), and ambiguous matches always go to review.
- Security: object-level permission checks (inaccessible objects return 404), CSRF protection,
  POST-only changes, append-only audit events, secure cookies/HTTPS in production.
- AI: structured Vertex AI (Gemini) tasks with Pydantic-validated output; every quoted piece
  of evidence must literally exist in the source, otherwise it goes to manual review.

### Be accurate in the video
- The AI results in the demo are **synthetic, hand-written cache fixtures**, not real Gemini
  output (no cloud credentials were available). Say "AI-assisted check" rather than showing it
  as live model output.
- The automatic sign-in is a **demo setting** for the hackathon (`BRON_DEMO_AUTOLOGIN`); a
  real deployment would use normal login/SSO.
