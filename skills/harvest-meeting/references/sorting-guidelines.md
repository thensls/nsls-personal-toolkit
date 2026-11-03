# Sorting Guidelines — Add / Not adding / Unsure

Step 6 sorts every candidate into exactly one of five buckets. The builder sees three lists;
SKIP and REJECT are counts. The goal is a short list the builder can approve in one
keystroke, not a long list they wave through.

| Bucket | Plain meaning | Goes in the KB? | What the builder sees |
|---|---|---|---|
| **ADD** | Useful and safe | Yes, on `yes` | ✅ list |
| **TRIM** | Useful, but one detail was personal, so that detail was cut | Yes, minus the detail | ✅ list, marked ✂ |
| **SKIP** | Harmless but trivial (small talk, logistics, undecided) | No | One count line; `show skipped` lists them |
| **REJECT** | Personal or harmful to someone if shared internally | No | Count by category; never the content |
| **UNSURE** | Can't tell without something only the builder knows | Only if named | ❓ list, max 4 |

SKIP and REJECT both stay out. The difference is *why*: SKIP is boring, REJECT is risky.

**Every decision carries a `reason`** of 12 words or fewer, in plain English ("names a
colleague's leave", "small talk about the offsite"). The builder can ask `why <N>` for any item.

**The test for everything:** *Will knowing this serve the company?* That is the main question.
Then: *Would it hurt a person, or break a promise to a partner, if a colleague read it?* The KB
is internal, read by NSLS staff only. Business facts are its whole point, including the
uncomfortable ones: deal sizes, prices, vendor terms, security gaps, open legal questions. Be
careful about **people**, not about **business**.

## Which rule wins

- **These guidelines replace the KB repo's sensitive-content rubric for harvest.** Where the
  two differ, follow these.
- **TRIM beats REJECT** when a real decision survives the cut. REJECT only when cutting leaves
  nothing.
- **A new page is sorted as one unit.** Its list fragments ("- shop revenue") ride with the page;
  don't SKIP them one by one. Open questions are fine to ADD when they're org-level.
- **Mixed items**: keep the decided part, cut the "exploring" clause (TRIM).
- **Being named is not a problem.** "Dana owns chapter onboarding", "Chris runs the load test",
  "Sam owns the crash fix" are all fine. See UNSURE for the one exception: a name tied to fault.
- **Today's date and the meeting date are given.** Use them to judge whether "we'll announce it
  Friday" has already happened.

## REJECT — never reaches the KB

Reject when the sensitive part *is* the point, so trimming would leave nothing useful. This list
is about protecting people; business information is not on it.

- **Individual pay and negotiations**: salary, bonus, equity grant, offer, raise, day rate, any
  comp conversation about a named or identifiable person (first name alone counts).
- **People decisions and judgments about a named person**: promotions, demotions, role or
  hours changes, performance, terminations, hiring offers in flight, "X isn't working out",
  criticism of a colleague, interpersonal friction.
- **Private life**: health, leave, family, mental health, personal finances, travel, career
  aspirations or frustrations voiced in a 1:1.
- **Profit and cash**: profit, margin, EBITDA, cash, runway, surplus. NSLS never shares profit
  internally. Revenue, deal sizes and budgets are fine.
- **Not yet announced**: reorgs, role changes, layoffs, M&A, succession, anything said as "don't
  share this yet" or "before we announce".
- **Secrets that grant access**: passwords, keys, tokens, or step-by-step ways to get into a
  system. Describing a security gap and who is fixing it is fine.
- **Member or student data**: names, emails, phone numbers, records of individual students.

## TRIM → ADD — keep the decision, cut the personal detail

Mark the item ✂ and say what was cut and why in a few words ("✂ name of colleague on leave").

- **Comp and equity program terms** → keep "an equity-rights program exists for eligible staff";
  cut vesting schedules, cliffs and cash-out terms.
- **A business fact carrying a personal aside** → keep the fact, cut the aside ("onboarding moves
  to Mei's team" stays; "because Jordan is overloaded" goes).
- **An announced change mixed with an unannounced one** → keep the announced part ("no layoffs
  are planned"), cut the reference to what hasn't been announced.

If after trimming the sentence no longer says anything useful, SKIP it.

## ADD — business information, including the uncomfortable kind

These are explicitly fine and useful. Don't trim them.

- Partner and deal details: school names, pricing per student, deal size, projected revenue,
  cohort dates, contract status.
- Vendor details: names, per-user prices, contract length, renewal plans.
- Security gaps and the work to close them ("several login paths aren't documented yet; Sam is
  documenting them").
- Open legal and compliance questions ("legal is still reviewing whether member data can go to
  the AI tool"; "the assessment names may carry copyright exposure").
- What partners or competitors are doing, including concerns ("this partner has copied our
  ideas before").
- Short-lived task owners ("Chris runs the load test by Oct 22"), standing practices, product
  metrics, scope decisions.

## SKIP — harmless, but not knowledge

Skip only these. When in doubt between SKIP and ADD, **ADD** — the ✅ list is approved with one
`yes`, so an extra harmless line costs the builder almost nothing.

- Small talk, scheduling, logistics.
- Ideas floated but not decided ("maybe we should", "worth exploring").
- Exact repeats of what the topic file already says (Step 5 catches most of these).

## UNSURE — at most 4, and zero is a good answer

Use UNSURE only when the call turns on something the model cannot know from the transcript:
*Has this been announced? Is this person's new scope public yet?* It is not a place for "I'd
rather not decide".

- **A named person tied to fault** — shown as the cause of a miss, delay, bug or failure, or as
  falling short — goes here with the name left in. Question: "Names Sam as the cause of the
  delay. Keep the name?" Don't trim it automatically.
- Write each as the text plus one question the builder can answer in a second.
- Rank by usefulness to the KB. If more than 4 qualify, keep the top 4 and REJECT the rest.
- Unanswered UNSURE items are rejected, never added.
- A Current State rewrite that the merge step says dropped real context goes to UNSURE.

## Meeting type changes the default

- **1:1s and small private meetings**: org-level facts and decisions are fine. Nothing about
  either person — their workload, pay, plans, leave, performance or feelings.
- **External calls**: normal rules. The partner's terms and numbers are useful business facts.
- **SLT and team meetings**: normal rules.

## Worked examples (synthetic)

| Candidate | Bucket | Why |
|---|---|---|
| "Society launch moves to February; Priya owns the waitlist" | ADD | Decision + ownership |
| "Pilot with Westbrook State projected at $180K and 4,000 members" | ADD | Deal facts are business knowledge |
| "We'll sign the analytics vendor at $0.40/user, two-year term" | ADD | Vendor terms are business knowledge |
| "Legal is still reviewing whether member data can go to the AI tool" | ADD | Open legal question the company should know |
| "Priya's raise is held until the reorg lands" | REJECT | Individual pay |
| "Sam has been out a lot since the surgery" | REJECT | Health |
| "Q3 margin dropped to 9%" | REJECT | Profit is never shared |
| "Maybe we should revisit chapter dues next year" | SKIP | Not decided |
| "Owen will take over Partnerships once we tell the team Friday" | UNSURE (if Friday has passed) or REJECT | Turns on the announcement |
| "The launch slipped because Sam missed the API deadline" | UNSURE | Name tied to fault; keep it? |
| "Equity-rights grants vest over four years with a one-year cliff" | TRIM → ADD | ✂ program terms |
