# Bug: morning "Plan your day" screen 500s — `plan.top3_est` missing in index() context

**Where:** live `pp-cli-visual` @ `2df8960` ("Add per-task time estimates (timeboxing)"), 3 commits past `48b97bb`.

**Symptom:** `GET /` returns **500** whenever the daily note is in the morning/plan state.

**Traceback (root):**
```
templates/_components/plan_your_day.html, line 91:
  value="{{ '%g'|format(plan.top3_est[i]) if plan.top3_est[i] else '' }}"
jinja2.exceptions.UndefinedError: 'dict object' has no attribute 'top3_est'
```
Render path: `index` (server.py:1022) → `day.html` → `_components/coach_morning.html` → `_components/plan_your_day.html:91`.

**Root cause:** the timeboxing commit added `plan.top3_est[i]` to `plan_your_day.html`, but the `plan` dict built for the `index()` / coach-morning render path does **not** include `top3_est`. `server.py` only sets `top3_est` in one plan-builder (≈ lines 443/448) — not the context that reaches the morning screen.

**Fix:** populate `top3_est` (and any sibling timeboxing fields, e.g. bonus estimates) in **every** `plan`/context dict that can reach `plan_your_day.html` — ideally by centralizing plan-dict construction so there's one builder. As a belt-and-suspenders, also guard the template: `plan.top3_est[i] if plan.top3_est is defined and plan.top3_est[i] else ''`.

**Regression test:** render the morning/coach-morning screen for a fresh open-day note (empty Top 3, no estimates) and assert 200 — this exact state is what 500s today.
