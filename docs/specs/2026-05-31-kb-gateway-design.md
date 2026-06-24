---
title: KB Gateway — credential-free KB writes for all SLT
type: feat
status: design
date: 2026-05-31
related: docs/specs/2026-05-29-kb-harvest-design.md
---

# KB Gateway — let every SLT member write to the Knowledge Base without GitHub

## Problem

The `/harvest-meeting` pipeline (shipped 2026-05-29/30) writes to `thensls/nsls-knowledge` by
running `git push` from each SLT member's **local clone** using **their personal git identity**.
That requires every SLT writer to have a personal GitHub account with push access to the private
repo and a local clone. Several SLT members have no GitHub access. Today they cannot contribute,
and the write path conflates two separate concerns:

- **Authorization** — "is this person allowed to write to the KB?" (should be: SLT allowlist + the
  per-edit approval gate)
- **The GitHub write** — "what credential pushes the commit?" (currently: the person's own GitHub
  account)

## Goal

Any of the 7 SLT members can run `/harvest-meeting` (or close-day Step 4c) and land approved,
rubric-gated edits in the KB **without holding any GitHub credential and without cloning the
repo**. Commit *authorship* still attributes to the individual member.

## Non-goals (v1)

- No Slack-approval path and no web UI. (The gateway's `/kb/commit` is designed so the SLT Coach
  bot *can* call it later for a Slack-only contributor flow — that is a separate project.)
- `--week-audit` write-actions stay out of the gateway for now (audit remains read-only/local).
- No change to the *thinking* half of the skill (extract/map/dedup/rubric/merge/approve).

## Decisions (locked during brainstorm 2026-05-31)

1. **Central commit proxy ("KB Gateway")**, not a shared token on laptops. No GitHub secret ever
   lives on an SLT laptop. Central audit + rotation. Foundation for a future Slack path.
2. **The gateway is the only thing that touches the repo — for reads too.** A no-GitHub member
   can't even clone the private repo, so the gateway serves read-context as well as performing
   writes. Laptops are fully GitHub-free.
3. **Edit application moves server-side.** Today's Step 8 file-editing logic (append to Key
   Decisions / merge-replace Current State / scaffold a new topic) runs in the gateway against
   **live** repo content, making the gateway the single authoritative writer and eliminating the
   "is my local clone stale?" failure mode.
4. **New service under the slt-coach project** — own repo (`thensls/kb-gateway`), deployed in the
   existing slt-coach Railway project, sharing its Doppler project and SLT identity conventions.
5. **Per-member gateway tokens** — each SLT member has their own bearer token (attribution +
   individual revocation + per-person audit), not one shared secret.
6. **Hard cut** — replace Step 8 with the gateway call; no permanent dual-path. Sequenced so the
   gateway is deployed and dry-run-validated *before* the skill is switched, so the harvest is
   never broken mid-flight.
7. **Dedicated GitHub App** for the gateway (the existing rippling-sync write path runs as Kevin's
   personal gmail identity — not reusable). App scoped to `nsls-knowledge` only, contents R/W.

## Architecture

```
Claude Code (each SLT laptop)              KB Gateway (Railway, slt-coach project)         GitHub
  /harvest-meeting                          ┌──────────────────────────────────┐
   Fathom MCP → extract→map→dedup→rubric     │ GET  /kb/context   (Bearer authz) │ GitHub App
     →merge→ numbered approval in Claude     │ POST /kb/commit    (Bearer authz) │ installation
   Code                                      │ GET  /kb/whoami    (Bearer authz) │ token (short-
   POST approved candidates + token  ──────► │ GET  /health                      │ lived) ──► thensls/
                                             │ • per-member token registry       │            nsls-knowledge
                                             │ • applies edits on LIVE repo       │ ◄── atomic commit
                                             │ • author = SLT member              │     (author = member,
                                             │ • committer = automation App       │      committer = bot)
                                             │ • audit log per commit             │
                                             └──────────────────────────────────┘
```

The Fathom transcript never leaves the laptop; only structured approved candidates (topic, section,
text, timestamps, merged Current State, base hashes, meeting metadata) are sent to the gateway.

## Components

### A. KB Gateway service (`thensls/kb-gateway`)

`aiohttp` Python service (matches slt-coach), deployed in the slt-coach Railway project, secrets in
the shared Doppler project. Endpoints:

- `GET /health` → `200 ok` (Railway healthcheck).
- `GET /kb/whoami` (Bearer) → `{email, name, is_slt}` for the token. Used by `/kb-setup` to validate.
- `GET /kb/context` (Bearer) → parses the repo at HEAD and returns:
  ```json
  {"head_sha": "...", "topics": { "<slug>": {"frontmatter":..., "current_state":..., "key_decisions":[...], "open_questions":[...]} }, "rubric": "<text from CLAUDE.md>"}
  ```
  (Same shape the skill caches to `/tmp/harvest-meeting-ctx/` today — parsing centralizes here.)
  Cacheable by `head_sha`.
- `POST /kb/commit` (Bearer) → body:
  ```json
  {"dry_run": false,
   "meeting": {"title":"...","url":"...","date":"YYYY-MM-DD"},
   "candidates": [
     {"topic_slug":"...","is_new_topic":false,"suggested_new":null,
      "section":"key_decisions|current_state|open_questions",
      "dedup_verdict":"NEW|REFINEMENT","replace_entry":null,
      "text":"...","fathom_timestamp_sec":0,
      "new_current_state":null,"current_state_base_sha256":null}
   ]}
  ```
  → response:
  ```json
  {"commit_sha":"...", "applied":[{"topic_slug":"...","status":"ok"}],
   "rejected":[{"topic_slug":"...","reason":"current_state base moved; re-harvest"}]}
  ```

**Write algorithm (race-safe, Git Data API):**
1. `GET git/ref/heads/main` → base commit sha; load base tree.
2. For each candidate: read the current target file from the base tree; apply the structured edit
   server-side (the ported Step 8 logic):
   - `key_decisions` / `open_questions` → insert `- {meeting.date}: {text} ([▶]({url}?timestamp={sec}))` under the section header (date is the **meeting** date). REFINEMENT → replace `replace_entry` in place.
   - `current_state` → **guard**: compute sha256 of the live Current State block; if it ≠
     `current_state_base_sha256`, reject this candidate (don't clobber). Else replace the block with
     `new_current_state`.
   - `is_new_topic` → scaffold once; subsequent candidates for the same new slug append (the
     accumulation fix). Acronym-aware title casing (AI, B2B, B2C, SNT, FOL, LTD, NSLS, KPI).
   - Bump `last-updated` frontmatter to today.
3. Create blobs → tree (base_tree + changed paths) → commit (`author` = member, `committer` =
   automation App, message `harvest: {date} {titles} (N edits)`) → `PATCH` ref (non-force).
4. On `422` (ref moved) → retry from step 1 against the new base (re-apply edits on latest). Bounded
   retries; surface a clear error if it keeps racing.
5. `dry_run: true` → run steps 1–2, return the would-be unified diff + applied/rejected, **no commit**.

Per-commit **audit row** (member email, topics, commit_sha, ts, dry_run) to a log/Airtable.

### B. `/harvest-meeting` skill changes (`nsls-personal-toolkit`)

- **Step 0** — drop the local-git-identity gate. Light pre-check: `KB_GATEWAY_TOKEN` present in env
  → else heartbeat "run `/kb-setup`". Real authorization is server-side. `kb_authors.txt` retired.
- **Step 1** — replace local-clone read + `git pull` with `GET /kb/context`; cache to
  `/tmp/harvest-meeting-ctx/` exactly as today (downstream steps unchanged).
- **Steps 2–7** — unchanged (Fathom load, extract, map, dedup, rubric, merge, numbered approval in
  Claude Code). Step 6b still computes `new_current_state` locally and now also records the
  `current_state_base_sha256` it merged against (from the `/kb/context` payload).
- **Step 8** — replace all local git with `POST /kb/commit`. Heartbeat the returned `commit_sha` and
  any per-candidate rejections (re-harvest hints). No local clone, no push.
- **close-day Step 4c / close-week Step 2b** — unchanged thin callers.

### C. Auth, identity, setup

- **Token registry** seeded in Doppler as `KB_TOKENS` (`{email: {token_hash, name}}`) for the 7 SLT;
  `is_slt` implied by registry membership. Rotation = update Doppler + the member's `.env`.
- **Per-member token** in each toolkit `.env`: `KB_GATEWAY_URL`, `KB_GATEWAY_TOKEN`.
- **`/kb-setup`** (extend `/connect` or `/personal-setup`): prompt for URL + token, validate via
  `GET /kb/whoami`, write to `.env`. Tokens minted by Kevin (admin) and shared via 1Password.

## Error handling

| Case | Gateway | Skill |
|---|---|---|
| Bad/expired token | 401 | "run `/kb-setup`" |
| Not in registry | 403 | "you're not an SLT writer" |
| `current_state` base moved | per-candidate reject (batch still commits the rest) | heartbeat "topic X moved — re-harvest it"; rest succeed |
| Ref race | retry on latest; error after N | surface, suggest re-run |
| GitHub API failure | 502 | retry once, then surface |
| Partial success | `applied[]` + `rejected[]` | report both per your no-silent-skip rule |

## Security

Dedicated GitHub App, contents R/W on `nsls-knowledge` only; private key in Doppler, never on a
laptop. Short-lived installation tokens minted per request. Per-member bearer tokens are
individually revocable and can only post rubric-gated, approval-gated, fully-revertable KB edits.
Central audit log. Member-supplied `new_current_state` is data, not code — committed verbatim; no
shell/`re.sub` backreference injection (use literal blob writes, not regex replacement strings).

## Testing

- Gateway unit tests for the ported edit logic (append, REFINEMENT, current_state guard + merge,
  new-topic accumulation, acronym title-casing) — reuse the synthetic-fixture expectations.
- `dry_run` returns the diff with no commit → the existing `/harvest-meeting` synthetic fixture
  validates the skill end-to-end against a dry-run gateway (no real write).
- Race test: simulate ref-move between read and PATCH → assert retry-on-latest + current_state guard.
- Auth tests: missing/expired/non-SLT token.

## Rollout (hard cut, safely sequenced)

1. Build + deploy the gateway; create the GitHub App; seed the 7 tokens in Doppler.
2. Validate against the live repo in `dry_run` (no writes) until the diffs match expectations.
3. Switch the skill's Step 1 + Step 8 to the gateway in one change; remove local-git from the
   harvest path. Issue tokens to all 7 SLT; run `/kb-setup` each.
4. Smoke test: Kevin runs a real one-candidate harvest through the gateway, verify the commit
   (author attribution, content) on GitHub.

## Open questions / follow-ups

- Audit sink: log file vs Airtable table vs Slack post. (Lean: a simple table or structured log v1.)
- `/kb/context` size (66 topics): fine at low volume; add `?topics=` filtering + head-sha caching if
  it gets heavy.
- Future: SLT Coach bot calls `/kb/commit` after a Slack approval → Slack-only contributors.
- Future: migrate token registry to the Airtable `is_slt` field as the source of truth.

## Work breakdown (for the plan)

1. Create the GitHub App (scoped to `nsls-knowledge`, contents R/W); install; store creds in Doppler.
2. Scaffold `thensls/kb-gateway` (aiohttp, Procfile, railway.toml, `/health`); deploy in slt-coach project.
3. Token registry + Bearer auth middleware + `/kb/whoami`.
4. `GET /kb/context` (repo parse → JSON; head-sha cache).
5. `POST /kb/commit` write algorithm (Git Data API, edit logic port, current_state guard, new-topic
   accumulation, acronym titles, ref-move retry, `dry_run`).
6. Audit logging.
7. Gateway tests (edit logic, race, auth, dry-run).
8. Skill changes: Step 0/1/8 rewire to the gateway; record `current_state_base_sha256` in Step 6b;
   retire `kb_authors.txt`.
9. `/kb-setup` + `.env` keys; issue + distribute the 7 tokens.
10. Dry-run validation against live repo; then hard-cut switch; smoke test; remove local-git path.
