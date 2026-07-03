# Local NSLS Knowledge Base

This is a **personal, local** knowledge base built by `/harvest-meeting`. It lives only on
this machine (local git repo, no remote) and is never pushed to the company KB. SLT members
write to the shared company KB instead; everyone else builds a KB here.

The same sensitive-content rubric applies. Keeping it uniform means nothing here would be a
problem if you ever choose to share or upstream an entry.

## Sensitive-Content Rubric — REQUIRED before every write

**The test:** *"Could this entry appear in an all-hands email or on the careers page without HR, Finance, Legal, or InfoSec flagging it?"* If no, drop the candidate or reshape it until yes.

**Never write to the KB:**

| Category | Examples |
|---|---|
| **Individual compensation** | Salaries, bonuses, equity/SARs grants tied to a named person, strike prices for specific grantees, OTE targets, day rates |
| **Personnel decisions about named individuals** | Promotions, demotions, role changes, transfers, performance ratings, terminations, hire-offers-in-flight, hours/comp adjustments, who was "let go" |
| **HR-sensitive matters** | Leave, accommodations, health, complaints/investigations, family circumstances, mental health, conduct issues |
| **Confidential financials** | **Profit / margin / EBITDA at any level (org, L1, L2, segment)** — total revenue numbers OK; profit numbers are NEVER shared internally even at the highest level. Also: cash balances, surplus, runway, individual deal economics, lender terms, board-only budget detail |
| **Security gaps** | Specific vulnerabilities, vendor dependencies that name the gap, active incidents, credentials, named single points of failure in security |
| **Active legal / regulatory** | Pending disputes, claims, investigations, settlement terms, audit findings before remediation |
| **Vendor / partner confidential terms** | Contract pricing, exclusivity clauses, partner-specific economics, named financial arrangements with consultants/partners |
| **Board-confidential moves** | Pending M&A, spinoff plans pre-announcement, succession discussions |

**OK to write:**

- Strategic direction, sequencing decisions, market focus
- Product roadmap themes and decisions
- Org structure as "who owns what surface" (NOT named promotions or comp)
- Programs at a level anyone can know exists ("SARs are part of the equity program" — never the grant amounts)
- Customer and market insights from shareable sources
- Process and operating model decisions
- Adoption metrics, product engagement numbers (when not tied to individual performance)
- Total revenue numbers (already broadly shared)

**Edge-case reshape rules:**

- Profit numbers → strip; keep the revenue figure
- Vendor names attached to gaps → drop the vendor; describe the dependency abstractly
- Named individuals tied to neutral org-ownership ("X owns surface Y") → OK
- Named individuals tied to status changes ("X promoted/let go/given Z") → NOT OK; reshape to the structural fact
- Specific dollar figures for non-revenue budget shortfalls → soften to "shortfall" without the figure
- Specific partner names attached to contract clauses → generalize to "B2B partner template includes [clause]"

If unsure, default to the safer reshape. One leak undermines trust more than ten missing entries.
