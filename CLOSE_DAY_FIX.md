# Fix: close-day must not infer the end-of-day pass is complete

**Bug (observed 2026-06-29):** With the companion running on the current day, the user said "close day" and the assistant synthesized + wrote the close **directly from the note's state** — because `End of Day: energy` was set and `<!--p:NN-->` progress markers existed. Those were set *during the day*. The user still had final items to mark. The Step 0.5 handshake (open Command Center in closing mode → wait for explicit "done") was skipped.

**Required behavior** — in companion mode, closing the **current day** with the companion running, close-day MUST:
1. Open the Command Center in closing mode (`/?closing=1`).
2. Surface the clickable `http://localhost:<port>/?closing=1` link.
3. **Block** until the user explicitly types "done" (or equivalent intent). A system/background notification is NOT "done."
4. Only then re-read the note and synthesize the close.

**Never** treat any of these as evidence the EOD pass is finished: `End of Day: energy` set · `<!--p:NN-->` progress markers · items in Done/Deleted/Deferred · an otherwise-populated note. All can be set mid-day.

**If the companion isn't running:** say so and offer to (re)start it + give the link, rather than silently closing from the note. Fall back to a chat close only if the user declines the companion.

**Suggested enforcement:** make Step 0.5 a hard, unskippable gate in the skill text (assertion-style), and add a *positive* signal instead of inference — e.g. the closing screen writes `closed_pass: true` (or a timestamp) to the note only on the explicit **Done** click, and close-day requires that marker before synthesizing.
