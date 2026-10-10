# Sorting Guidelines — Add / Not adding / Unsure

Step 6 sorts every candidate into exactly one of four buckets. The builder sees three of
them; the fourth is a count. The goal is a short list the builder can approve in one
keystroke, not a long list they wave through.

| Bucket | What the builder sees | Default |
|---|---|---|
| **ADD** | Bulleted list, approved together | Added on `yes` |
| **TRIM → ADD** | Same list, marked ✂ with what was cut | Added on `yes` |
| **REJECT** | Count by category, no content | Never added |
| **SKIP** | One count line | Never added |
| **UNSURE** | At most 4, each with a one-line question | Rejected unless the builder says add |

**The test for everything:** *Could this appear in an all-hands email without HR, Finance,
Legal or InfoSec flagging it?* And: *Would someone on another team look this up in three
months?* ADD needs yes to both.

## Which rule wins

- **TRIM beats REJECT** when a real decision survives the cut ("rollout waits on renaming the
  assessments" survives cutting the copyright detail). REJECT only when cutting leaves nothing.
- **A new page is sorted as one unit.** Its list fragments ("- shop revenue") ride with the page;
  don't SKIP them one by one. Open questions are fine to ADD when they're org-level.
- **Trimming covers names everywhere**: file names, slugs, titles and tags, not just the text.
- **Mixed items**: keep the decided part, cut the "exploring" clause (TRIM).
- **Pricing or deal strategy with no named partner or vendor** is fine ("B2B is free in
  exchange for multi-year commitments").
- **Creating an empty role** ("we're hiring a Head of Product") is fine. Moving a named person,
  or restructuring teams, before it's announced is REJECT or UNSURE.
- **Today's date and the meeting date are given.** Use them to judge whether "we'll announce it
  Friday" has already happened.

## REJECT — never reaches the KB

Reject when the sensitive part *is* the point, so trimming would leave nothing useful.

- **Individual pay and negotiations**: salary, bonus, equity grant, offer, raise, day rate, any
  comp conversation about a named or identifiable person (first name alone counts).
- **People decisions and judgments about a named person**: promotions, demotions, role or
  hours changes, performance, terminations, hiring offers in flight, "X isn't working out",
  criticism of a colleague, interpersonal friction.
- **Private life**: health, leave, family, mental health, personal finances, travel, career
  aspirations or frustrations voiced in a 1:1.
- **Money beyond revenue**: profit, margin, EBITDA, cash, runway, surplus, budget shortfalls
  with figures, lender or board budget detail. Total revenue and adoption numbers are fine.
- **Deal and vendor terms**: pricing, contract length, renewal strategy, discounts,
  exclusivity, or projected revenue tied to a *named* partner, school or vendor.
- **Security**: specific gaps, undocumented access paths, active incidents, credentials,
  named single points of failure.
- **Legal and compliance exposure not yet resolved**: disputes, investigations, pending legal
  review, IP or copyright exposure, a certification that is incomplete while attested to.
- **Not yet announced**: reorgs, role changes, M&A, succession, anything said as "don't share
  this yet" or "before we announce".
- **Gossip about a named outside organization**: "they copy our ideas", "their team is weak".
- **Member or student data**: names, emails, phone numbers, records of individual students.

## TRIM → ADD — keep the decision, cut the detail

Most past near-misses were good decisions carrying one bad detail. Cut the detail and add.
Mark the item ✂ and name what was cut in three words or fewer ("✂ deal figure").

- Named deal + revenue projection → keep "partnership with a large public university in
  negotiation"; drop the school and the figures.
- Vendor + price or term → keep "evaluating a data vendor for X"; drop name, price, term.
- Security fix with the gap described → keep "auth work includes documenting login paths";
  drop how many paths are undocumented and who is exposed.
- Program terms → keep "an equity-rights program exists for eligible staff"; drop vesting,
  cliffs, cash-out terms.
- Named person owning an area → fine as-is ("Dana owns chapter onboarding") **unless** it is
  part of an unannounced change, then REJECT.

If after trimming the sentence no longer says anything useful, SKIP it.

## SKIP — not sensitive, not worth an entry

Silent except for one count. Skip:

- Ideas floated but not decided ("maybe we should", "worth exploring").
- Status with no change, restated known facts, small talk, scheduling, logistics.
- Action items that only matter to the people in the room this week.
- Anything already in the topic file (Step 5 catches most of these).

Be strict here: this bucket is what keeps the ADD list short.

## UNSURE — at most 4, and zero is a good answer

Use UNSURE only when the call turns on something the model cannot know from the transcript:
*Has this been announced? Is the partner OK with this being known? Is this person's new scope
public yet?* It is not a place for "I'd rather not decide".

- Write each as the trimmed text plus one question the builder can answer in a second.
- Rank by usefulness to the KB. If more than 4 qualify, keep the top 4 and REJECT the rest.
- Unanswered UNSURE items are rejected, never added.
- A Current State rewrite that the merge step says dropped real context goes to UNSURE.

## Meeting type changes the default

- **1:1s and small private meetings**: only org-level decisions both people clearly agreed
  to. Nothing about either person. Expect most 1:1s to produce zero ADDs — that is correct.
- **External calls**: the partner's terms, numbers and opinions are theirs, not ours. Keep only
  our own process decisions.
- **SLT and team meetings**: normal rules.

## Worked examples (synthetic)

| Candidate | Bucket | Why |
|---|---|---|
| "Society launch moves to February; Priya owns the waitlist" | ADD | Decision + public ownership |
| "Priya's raise is held until the reorg lands" | REJECT | Individual pay |
| "Pilot with Westbrook State projected at $180K and 4,000 members" | TRIM → ADD | ✂ school + figures |
| "We'll sign the analytics vendor at $0.40/user, two-year term" | TRIM → ADD | ✂ vendor terms |
| "Maybe we should revisit chapter dues next year" | SKIP | Not decided |
| "Owen will take over Partnerships once we tell the team Friday" | UNSURE (if Friday has passed) or REJECT | Turns on the announcement |
| "Legal is still reviewing whether member data can go to the AI tool" | REJECT | Unresolved legal |
| "We ship the new induction email next sprint" | ADD | Decision |
| "Sam has been out a lot since the surgery" | REJECT | Health |
