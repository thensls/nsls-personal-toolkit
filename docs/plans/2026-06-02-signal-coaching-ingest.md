---
title: Signal Coaching Ingest — Plan
type: feat
status: planned
date: 2026-06-02
plan_depth: deep
spec: ../specs/2026-06-02-signal-coaching-ingest-design.md
extends: 2026-05-16-manager-coaching-person-intelligence.md
---

# Signal Coaching Ingest — Plan

## Overview

Make person-intelligence **Signal-aware** and turn that signal into manager behavior. Each direct
report's profile gains a distilled `## Signal Read` (wins, friction themes, sentiment, goal health,
submission cadence) sourced from their Quick Notes; `/open-day` and `/open-week` gain a
**Management lane** that surfaces, every period, the three jobs great managers do: **celebrate,
develop, remove friction** — each tied to a named report and a specific signal.

See the design doc for data model, the sensitivity boundary, and the distillation contract.

## Problem frame

The v2 manager-coaching system (2026-05-16, completed) made profiles multi-source (Fathom + Slack +
Gmail) and surfaced coaching actions in open-day/week. But the richest, most current signal about
how each report is actually doing — their own weekly Quick Notes — was never connected. Coaching
goals are built from 1:1 transcripts and Airtable goals; they're blind to what the person said this
week about their wins and friction. Meanwhile the company's stated strategy is to prove Quick Notes
matter by having managers act on them. The loop is open.

## Decisions locked (Kevin, 2026-06-02)

- **D1 — Distilled in vault.** Raw Quick Notes cache-only; only rubric-filtered distillation reaches `30-people/`.
- **D2 — Direct reports only.** Coaching scope = `tracking_reason == "direct_report"` from `org-chart.json`.
- **D3 — Phase the headless question.** Phase 1 = MCP-in-session (immediate value, validates safety). Phase 1.5 = token-based `fetch_signal.py` so the cron sweep is self-sufficient (no knowingly two-speed system).
- **D4 — Cadence threshold N = 2 weeks** for "no 1:1 / stopped submitting" flags.

## Requirements trace

- **R1.** Signal becomes a 4th ingest source; `sources:` frontmatter records `signal`.
- **R2.** Raw Quick Notes narration is cached only (gitignored, TTL); never written to the vault. (D1)
- **R3.** A reusable distillation step applies the KB Sensitive-Content Rubric before any Signal-derived text reaches a profile.
- **R4.** Coaching scope is direct reports; org-wide wins/friction may inform the weekly digest only. (D2)
- **R5.** `/open-day` surfaces a Management lane (celebrate / develop / unblock) keyed to today's people, with a live freshness pull and a streak-≥3 → Top-3 candidate rule.
- **R6.** `/open-week` surfaces a Management cadence lane off `signal_team_summary`: week pulse, 3 intentions (1 per bucket, distributed), cadence audit (N=2), coaching-goal progress, loop-closure review.
- **R7.** Cadence flags fire at 2 weeks for both 1:1 gap and stopped-submitting. (D4)
- **R8.** The cron biweekly sweep is Signal-aware without a human in the loop. (D3, Phase 1.5)
- **R9.** Coaching goals stay AI-proposed / Kevin-approved; Signal only adds dated, theme-level evidence.
- **R10.** Loop-closure: surfaced friction that was acted on prompts a "tell the person what changed" task; unclosed loops roll forward.

## Phasing & build tasks

### Phase 1 — Profiles become Signal-aware (MCP-in-session) — highest value, lowest risk
- [x] Cache schema + path `~/.cache/person-intelligence/signal/<slug>.json` (cache lives under ~/.cache, outside repo+vault; write-guard refuses vault paths; 30-day TTL field).
- [x] `fetch_signal.py` v1 — normalizer + cache writer + mechanical sensitivity pre-filter + `--list-reports` (direct-report scoping). Tested: ER/family line dropped, real wins/friction kept after lexicon precision fix.
- [x] Extend `synthesize_profile.py` — accepts `signal`; renders the distilled (pre-screened) block; emits `## Signal Read`; coaching evidence as `<!-- DIGEST -->` (not into curated Coaching Goals); `sources += signal`.
- [x] Gate documented (`SIGNAL_INGEST=1`, direct reports only) in SKILL.md + Ingest Sources table. Flag NOT yet enabled in `.env` (Kevin's call).
- [~] Acceptance gate: ran on **Brandon Evans** (real LLM) → leak scan clean, `## Signal Read` distilled, 2 DIGEST suggestions, written to `/tmp` not the vault. **Awaiting Kevin's review + 1–2 more reports before enabling on real profiles.**

### Phase 1.5 — Headless parity (cron self-sufficiency) (D3)
- [ ] Investigate the Signal/employee-profiles read surface (REST endpoints the MCP wraps, or scoped Supabase read replica `obsfxvtflbmrfjcbmxoj`).
- [ ] `fetch_signal.py` v2 — token-direct path so `biweekly_sweep.py` (cron) pulls Signal with no MCP.
- [ ] `biweekly_sweep.py` — add `signal_available` to the manifest.

### Phase 2 — `/open-day` Management surfacer (R5)
- [ ] Add the Management lane section (celebrate / develop / unblock) keyed to today's people.
- [ ] Live `signal_wins/friction(weeks=1)` pull filtered to today's direct reports.
- [ ] Streak-≥3 friction → Top-3 Management candidate; cadence flag at N=2 wks.

### Phase 3 — `/open-week` Management cadence lane (R6)
- [ ] Pull `signal_team_summary`; render week pulse.
- [ ] Three-intentions prompt (1 celebrate / 1 develop / 1 unblock, distributed across reports).
- [ ] Cadence audit + coaching-goal progress review.

### Phase 4 — Loop-closure tracking (R10) — hardest, highest culture payoff
- [ ] Track surfaced friction → resolution → "told the person" state across weeks.
- [ ] Unclosed loops roll forward as P1 in open-week.

## Verification
- **Safety gate (blocking):** on a real report with known-sensitive Quick Notes, confirm the raw stays in cache and the vault profile contains only rubric-safe distillation. Manual review by Kevin before Phase 1 ships to all reports.
- **Cadence:** simulate a 2-week 1:1 gap and a stopped-submitting report; confirm both flag.
- **Headless:** run `biweekly_sweep.py` in a stripped `env -i` shell (as the .env-loader fix is tested) and confirm Signal data still flows (Phase 1.5).
- **No two-speed drift:** a cron-built profile and a hand-built profile for the same report carry the same `## Signal Read` freshness.

## Open questions
- Signal read surface for headless: does a REST API exist, or do we read Supabase directly? (Phase 1.5 spike.)
- Recognition mode per person (public channel vs DM) — pull from profile, or ask once and store?
- Should loop-closure state live in the profile, the cache, or a small `03-meta/` ledger?
