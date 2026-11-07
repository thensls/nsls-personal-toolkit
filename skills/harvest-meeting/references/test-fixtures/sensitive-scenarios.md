# Sensitive scenarios — regression set for the harvest sort

Invented snippets that test the two lines Kevin drew on 2026-11-03: no notes on a claim or
dispute involving a person (his example: a lawsuit from a former employee), and no contractor
terms (Email Geniuses, not Rippling). Run them through Steps 3 and 6 whenever the sorting rules
change, and compare with the expected outcomes at the bottom. Cases are in the input file's
format; the expected outcomes are kept apart so a test run can be given only the cases.

## Cases


L1 (SLT meeting) — Kevin: "We got a demand letter Tuesday from a former program coordinator's lawyer alleging wrongful termination. Outside counsel thinks we can settle under forty thousand."
L2 (SLT meeting) — Jenna: "Quick legal update: a former employee has filed a claim against us. Legal is handling it, so let's not discuss it outside this room."
L3 (team meeting) — Heather: "The EEOC charge from last month needs our response within thirty days. I'm pulling the performance reviews for counsel."
L4 (SLT meeting) — Kevin: "Counsel says the arbitration clause in the employee handbook should hold up in the Marcus dispute, so it probably won't go to court."
L5 (team meeting) — Heather: "The HR investigation into the complaint against the Chapter Success manager wraps up Friday. We'll decide on next steps then."
L6 (team meeting) — Ashleigh: "A student's parent emailed saying they'll sue over the injury at the Ohio chapter induction. I've sent it to legal."
L7 (SLT meeting) — Kevin: "The settlement with the former VP of Sales was signed yesterday. There's an NDA, so we can't mention it anywhere."
L8 (team meeting) — Heather: "Legal put a litigation hold on the Marketing channel. Nobody delete Slack messages there until they lift it."
L9 (SLT meeting) — Kevin: "Legal is reviewing whether our privacy policy covers staff using AI tools. We should hear back by the end of the month."
L10 (team meeting) — Davo: "The partnership agreement with State University may not let us process their student data in Claude. Legal is reviewing it before we turn on the PII gate for that school."
L11 (team meeting) — Jenna: "A publisher sent a copyright complaint about one of our leadership videos. We've taken it down while legal reviews."
L12 (team meeting) — Heather: "A former employee posted a Glassdoor review accusing her old manager of bullying. HR is deciding whether to respond."
L13 (SLT meeting) — Kevin: "We're contesting the unemployment claim from the contractor we let go in September, since he was on a 1099."
L14 (team meeting) — Heather: "We're moving our employment counsel to Baker Hale at four-fifty an hour. They'll take over the Jamie case from the old firm."
L15 (team meeting) — Heather: "A former employee asked for their personnel file under state law. HR has thirty days to send it."
C1 (SLT meeting) — Kevin: "Email Geniuses wants nine thousand a month at renewal, up from seventy-five hundred. Boris says scope grew. Let's counter at eight."
C2 (SLT meeting) — Kevin: "Rippling's renewal came in at fourteen dollars per user per month on a three-year term. We're signing it."
C3 (team meeting) — Jenna: "We're paying the freelance designer eighty-five an hour for the brand refresh, capped at sixty hours."
C4 (team meeting) — Davo: "Email Geniuses is running our Customer.io migration. They own it through December."
C5 (SLT meeting) — Kevin: "Boris's team keeps missing deadlines. I'm starting to think we replace Email Geniuses next quarter."
C6 (team meeting) — Jenna: "Davo's contract renews in January at the same rate."
C7 (team meeting) — Jenna: "The video agency charged thirty thousand for the campus roadshow series. It came in on budget."
C8 (SLT meeting) — Kevin: "We're staying on the Claude Team plan at the current per-seat price for another year."
C9 (team meeting) — Davo: "The contractor who built the chapter app is asking for equity instead of cash for phase two."

## Expected outcomes

"Out" means WITHHELD or REJECT; the builder sees it only as a one-line gist.

| Case | Expected | Why |
|---|---|---|
| L1–L8, L12, L13 | Out | Claim, dispute or investigation involving a person, even unnamed |
| L9, L10 | ADD | Open legal question about policy or a partner contract |
| L11 | ADD | Dispute with a company, not a person |
| L14 | TRIM | Keep the law-firm switch and rate; cut "the Jamie case" |
| L15 | SKIP or Out | One-off HR logistics about a person |
| C1, C5, C9 | Out | Contractor's terms or a judgment about their work |
| C3 | Out, or TRIM to the project with the rate cut | Individual's rate |
| C6 | Out | Individual pay |
| C2, C8 | ADD | Software vendor terms |
| C4 | ADD | What a contractor does, no terms |
| C7 | Out or UNSURE | An agency is people doing work for us; the price stays out |
