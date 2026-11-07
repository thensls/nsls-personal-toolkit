---
date: 2026-11-07
slug: harvest-legal-and-contractors
last_commit: 95430c2eac1173bb6c3ce6afa26d5150054c117a
skills_changed: [harvest-meeting]
files_changed: 4
cost_to_adopt: "2 min"
breaking: false
---

# Harvest keeps legal claims and contractor terms out

## Why

Contractors can read the knowledge base, and a legal claim about a person is easy to trace back
to them even with the name removed. A test of 24 invented cases found harvest keeping notes on a
former employee's demand letter, an agency charge, a litigation hold and a contractor's renewal
negotiation, because "open legal questions" and "vendor terms" were on its keep list.

## What Changed

- **Claims and disputes involving a person stay out**: lawsuits, demand letters, HR complaints
  and investigations, settlements, litigation holds, and counsel's advice about them, even with
  the name removed. A legal question about a policy, a partner contract or a copyright complaint
  from another company is still kept.
- **Contractors' terms stay out**: rates, renewals, negotiations and judgments about their work.
  No list of contractors is needed. Harvest asks "is this people doing work for us, or a product
  we buy?" Software prices such as Rippling's are still kept, and so is what a contractor is
  working on.
- **A regression set of the 24 cases** ships with the skill, so the next rule change can be
  checked against them.

## Cost to Adopt

**2 min.** Arrives on its own at your next session.

## Safe Merge

It changes one skill's reference files; your own edits to them are kept.

## Opt-Out Guide

- Say "turn off KB harvest" to stop the daily harvest.
