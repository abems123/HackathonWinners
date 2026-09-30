# Implementation decisions

The repository originally contained only an implementation plan labelled README.md. Its referenced product specification (sections 10 and 15, among others) was absent. The original is preserved in docs/implementation-plan.md. This implementation follows its explicit requirements; the decisions below fill gaps conservatively.

- Django 5.2 is retained. Python 3.11 is supported as well as the proposed 3.12, matching the available runtime.
- Latest means highest ingested version, even before its effective date. The UI displays dates separately.
- Exceptions require a trustworthy base, including its open doubts, not merely its version/hash. This strengthens the supplied algorithm: a confirmed conflict on a base cannot leave an exception green.
- Only owners/admins on the responsible layer team may change layer verdicts. Team membership alone does not elevate a consultant.
- Missing, ambiguous, deleted or changed passages require an explicit new quote and human confirmation. Confirmation cannot silently reuse an obsolete anchor.
- Possible conflicts cannot be dismissed through general confirmation. They require a reasoned dismissal or escalation first. Reconfirming a stale pin cannot silently hide an existing conflict.
- Dismissal is restricted to QUESTION, AI_SUGGESTED, POSSIBLE_CONFLICT, and SOURCE_OUTDATED. A reason is mandatory for every action.
- An expert can answer an assigned question through a minimal question view, but that assignment does not grant access to the client or other pins.
- Audit events are append-only through the application and admin. Database administrators remain capable of altering the database; external immutable archival is a deployment responsibility.
- AI cache fixtures are explicitly marked synthetic until generated with real Vertex credentials. No fabricated model provenance or Aikido results are claimed.
- Aikido screenshots, a submitted demo video, and real Vertex cache generation require external accounts/credentials and are tracked separately from the working website.
- Layer knowledge is organisation-wide and readable by consultants/owners/admins, so wrong-country material can be explained as outside scope. Client sources and exceptions require an explicit client assignment or oversight of that client's subscribed layer. A layer-owner role alone does not grant access to every client.
- A pin that is excluded or superseded cannot hold its assumptions. Dependent exceptions therefore fail safe even if no ripple doubt has been written yet.
- Assigned questions can be answered by the assigned human regardless of their normal client access. Expert dashboard/queue entries omit client and source labels; the restricted question view contains only the question and exact passage.
