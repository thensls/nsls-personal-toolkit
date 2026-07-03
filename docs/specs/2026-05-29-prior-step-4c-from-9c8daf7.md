# Prior Step 4c (extracted from 9c8daf7 / 2026-05-25)

This is the last committed state of Step 4c (Knowledge Graph Insight Proposals) before it was accidentally removed in commit 6a1dd15 (Apple Health 1f-bis port) on 2026-05-28.

Source: `git show 9c8daf7:skills/close-day/SKILL.md` lines 654-737.

Extracted on 2026-05-29 during reconciliation when the spec was discovered to be based on the false premise that no harvest pipeline existed.

---

### Step 4c: Knowledge Graph Insight Proposals

The goal of `60-nsls-knowledge/` is to reflect **how NSLS works and where it's going**, so any employee can read the topic files and understand the company's strategy, direction, and current state. Treat this step as the daily contribution to that picture.

If `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge/` exists, scan today's meetings and reading for potential knowledge graph contributions.

1. **Match topics**: Compare today's meeting summaries, Familiar screen activity, and conversation context against the topic files in `60-nsls-knowledge/`. Look for topic name matches, related keywords, and frontmatter `related:` links.

2. **Filter for insights**: For each matched topic, ask: **"Would a new team member at NSLS want to know this to understand how NSLS works or where it's going?"** If yes, it's a candidate. Examples of what qualifies:
   - A decision or direction that shapes how something operates ("We're routing X through Y now")
   - A current-state update — the topic moved forward, changed, or stalled in a way that matters
   - A surprising data point, number, or example that anchors the topic
   - A framework, mental model, or definition that clarifies how a thing works
   - A debate or trade-off with specific positions — useful for understanding *why* we do what we do
   - An open question being actively worked

   Lower the bar from "novel insight" to "would help an NSLS employee understand the strategy." Most close-days should have at least one candidate.

3. **Apply the sensitive-content filter — HARD STOP, runs before any candidate is surfaced.**

   The KB is intended for all NSLS employees. The test: *"Could this entry appear in an all-hands email or on the careers page without HR, Finance, Legal, or InfoSec flagging it?"* If no, drop the candidate or reshape it until yes.

   **Never write to the KB:**

   | Category | Examples |
   |---|---|
   | **Individual compensation** | Salaries, bonuses, equity/SARs grants tied to a named person, strike prices for specific grantees, OTE targets, day rates |
   | **Personnel decisions about named individuals** | Promotions, demotions, role changes, transfers, performance ratings, terminations, hire-offers-in-flight, hours/comp adjustments, who was "let go" |
   | **HR-sensitive matters** | Leave, accommodations, health, complaints/investigations, family circumstances, mental health, conduct issues |
   | **Confidential financials** | **Profit / margin / EBITDA at any level (org, L1, L2, segment)** — total revenue numbers OK, but profit numbers are NEVER shared internally even at the highest level. Also: cash balances, surplus, runway, individual deal economics, lender terms, board-only budget detail |
   | **Security gaps** | Specific vulnerabilities, vendor dependencies that name the gap, active incidents, credentials, named single points of failure in security |
   | **Active legal / regulatory** | Pending disputes, claims, investigations, settlement terms, audit findings before remediation |
   | **Vendor / partner confidential terms** | Contract pricing, exclusivity clauses, partner-specific economics, named financial arrangements with consultants/partners |
   | **Board-confidential moves** | Pending M&A, spinoff plans pre-announcement, succession discussions |

   **OK to write:**
   - Strategic direction, sequencing decisions, market focus
   - Product roadmap themes and decisions
   - Org structure as "who owns what surface" (NOT named promotions or comp)
   - Programs at a level anyone can know exists (e.g., "SARs are part of the equity program" — never the grant amounts)
   - Customer and market insights from shareable sources
   - Process and operating model decisions
   - Adoption metrics, product engagement numbers (when not tied to individual performance)
   - Total revenue numbers (already broadly shared)

   **Edge-case reshape rules:**
   - Profit numbers → strip; keep the revenue figure
   - Vendor names attached to gaps → drop the vendor; describe the dependency abstractly
   - Named individuals tied to neutral org-ownership ("X owns surface Y") → OK
   - Named individuals tied to status changes ("X was promoted/let go/given Z") → NOT OK; reshape to the structural fact ("dedicated full-time lead in place", "restructured for X")
   - Specific dollar figures for budget shortfalls in non-revenue contexts → soften to "shortfall" without the figure
   - Specific partner names attached to contract clauses → generalize to "B2B partner template includes [clause]"

   If you're unsure, default to the safer reshape. The KB compounds in value as it grows trustworthy — one leak undermines that more than ten missing entries.

4. **Surface up to 3 candidates** with specific evidence:
   ```
   📚 Knowledge Graph

     You had a detailed exchange with Ashleigh about chapter health.
     She argued advisor turnover is the primary driver of stale chapters,
     citing UPhoenix and two other examples. This shifts the working
     model from event frequency to advisor stability.

     → Add to [[chapter-health]] Key Decisions? (y/n)
   ```

5. **If approved**, append a dated one-liner to the topic file:
   - Decisions → `## Key Decisions` section
   - State changes → `## Current State` section
   - Format: `- YYYY-MM-DD: [One sentence with specific evidence]`

6. **Heartbeat — always surface one line, even on 0-candidate days.** Silent skips make a working skill and a broken skill look identical. Print one of:
   ```
   📚 Knowledge Graph: scanned [N] meetings against [M] topics — [K] candidates proposed.
   ```
   ```
   📚 Knowledge Graph: scanned [N] meetings against [M] topics — nothing met the bar today.
   ```
   ```
   📚 Knowledge Graph: skipped — `$OBSIDIAN_VAULT_PATH/60-nsls-knowledge/` not found.
   ```
   This line goes into the daily note's End of Day section so you can audit whether the step ran at all over time.

