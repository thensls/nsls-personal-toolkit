#!/usr/bin/env python3.12
"""
fetch_signal.py — Signal (Quick Notes) ingest for person-intelligence (Phase 1).

Phase 1 is MCP-in-session: the orchestrating Claude session calls the signal_*
MCP tools, bundles their raw JSON, and pipes it here. This script is the pure,
testable normalizer + cache writer. It does NOT call MCP itself (a Python script
can't reach MCP tools); Phase 1.5 will add a token-direct fetch path for the
headless cron sweep.

Two responsibilities:
  1. Persist the RAW Signal bundle to ~/.cache/person-intelligence/signal/<slug>.json
     — cache only, NEVER the Obsidian vault (Quick Notes carry HR/health/comp content).
  2. Emit a NORMALIZED, synthesis-ready JSON to stdout: sentiment trajectory, wins,
     friction themes (with streaks), goal health, submission cadence — each item
     mechanically screened for sensitivity so downstream surfacers (open-day) can
     suppress raw display even if they skip the LLM rubric pass.

Modes:
  --list-reports                 Print direct-report slugs (JSON) from list_relationships.py
  --slug X [--weeks N]           Normalize: read raw MCP bundle from stdin, cache it, emit normalized JSON

Input bundle (stdin, --slug mode):
  {"slug": "...",
   "person":  <signal_person output | null>,
   "history": <signal_person_history output | null>,
   "goals":   <signal_person_goals output | null>}

Status → stderr. Normalized JSON → stdout.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

CACHE_ROOT = pathlib.Path.home() / ".cache" / "person-intelligence" / "signal"
TTL_DAYS = 30
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# --- Phase 1.5: token-direct Signal API (mirrors employee-profiles mcp-server) ---
SIGNAL_BASE_URL = os.environ.get(
    "SIGNAL_API_URL", "https://employee-profiles-production.up.railway.app"
).rstrip("/")


def load_signal_token() -> str:
    tok = (os.environ.get("SIGNAL_API_TOKEN") or "").strip()
    if tok:
        return tok
    cfg = os.environ.get("XDG_CONFIG_HOME")
    token_file = (pathlib.Path(cfg) / "nsls" / "signal-token") if cfg \
        else (pathlib.Path.home() / ".config" / "nsls" / "signal-token")
    try:
        tok = token_file.read_text().strip()
    except FileNotFoundError:
        raise SystemExit(f"No Signal token. Set SIGNAL_API_TOKEN or create {token_file} (/signal-setup).")
    if not tok:
        raise SystemExit(f"Signal token file {token_file} is empty (/signal-setup).")
    return tok


def _signal_get(path: str, params: dict | None = None, token: str | None = None):
    token = token or load_signal_token()
    url = SIGNAL_BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_bundle(slug: str, weeks: int) -> dict:
    """Token-direct pull of the three per-person endpoints (no MCP needed)."""
    token = load_signal_token()
    enc = urllib.parse.quote(slug)
    bundle = {"slug": slug}
    try:
        bundle["person"] = _signal_get(f"/api/mcp/person/{enc}", token=token)
    except Exception as e:
        log(f"{slug}: person fetch failed: {e}"); bundle["person"] = None
    try:
        bundle["history"] = _signal_get(f"/api/mcp/person/{enc}/history", {"weeks": weeks}, token=token)
    except Exception as e:
        log(f"{slug}: history fetch failed: {e}"); bundle["history"] = None
    try:
        bundle["goals"] = _signal_get(f"/api/mcp/person/{enc}/goals", {"weeks": weeks}, token=token)
    except Exception as e:
        log(f"{slug}: goals fetch failed: {e}"); bundle["goals"] = None
    return bundle


def fetch_team_summary(manager_slug: str | None = None, week: str | None = None) -> dict:
    """Token-direct weekly team pulse (submissions, friction+streaks, wins, deltas)."""
    return _signal_get("/api/mcp/team-summary", {"manager": manager_slug, "week": week})

# --- Sensitivity pre-filter -------------------------------------------------
# Mechanical first line of defense. The synthesizer's LLM rubric pass is the
# second. Anything matching here is flagged sensitive=True: excluded from the
# structured wins/friction surfaced to open-day, and marked so the synthesizer
# drops or themes it. Intentionally broad — false positives just get human review.
SENSITIVE_PATTERNS = [
    # health / medical
    r"\bER\b", r"emergency room", r"hospital", r"\bICU\b", r"surgery", r"surgical",
    r"diagnos", r"cancer", r"chemo", r"tumor", r"illness", r"\bsick\b", r"symptom",
    r"mental health", r"therap", r"depress", r"anxiet", r"burn(ed)?\s*out", r"medical",
    r"disab", r"injur",
    # family / personal life events
    r"\bdad\b", r"\bmom\b", r"\bfather\b", r"\bmother\b", r"\bspouse\b", r"\bwife\b",
    r"\bhusband\b", r"famil", r"divorce", r"custody", r"funeral", r"passed away",
    r"\bdied\b", r"\bdeath\b", r"pregnan", r"maternity", r"paternity", r"bereave",
    # comp / employment status
    r"salar", r"compensation", r"\bcomp\b", r"\braise\b", r"bonus", r"equity",
    r"\bfired\b", r"laid off", r"layoff", r"\bquit\b", r"resign", r"\bPIP\b",
    r"terminat", r"severance",
    # conduct / legal — only unambiguous HR/legal terms; "investigation" and bare
    # "complaint" are excluded: they collide with everyday engineering/CS work
    # ("bug investigation", "customer complaint"). The LLM rubric pass in
    # synthesize_profile.py is the backstop for anything reaching the vault.
    r"harass", r"grievance", r"lawsuit", r"discrimin", r"\bHR complaint\b",
]
_SENS_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)


def is_sensitive(text: str | None) -> bool:
    return bool(text) and bool(_SENS_RE.search(text))


def log(msg: str) -> None:
    print(f"[fetch_signal] {msg}", file=sys.stderr)


# --- direct-report scoping --------------------------------------------------
def slugify(name: str) -> str:
    return name.lower().replace("'", "").replace(".", "").replace(" ", "-")


def list_reports() -> list[dict]:
    """Direct reports (tracking_reason == direct_report) via list_relationships.py."""
    env = dict(os.environ)
    env.setdefault(
        "OPERATING_USER_EMAIL",
        env.get("BUILDER_EMAIL", ""),
    )
    out = subprocess.check_output(
        ["python3.12", str(SCRIPT_DIR / "list_relationships.py")],
        env=env, text=True, stderr=subprocess.DEVNULL,
    )
    data = json.loads(out)
    reports = []
    for r in data.get("relationships", []):
        if r.get("tracking_reason") == "direct_report":
            reports.append({"name": r["name"], "slug": slugify(r["name"])})
    return reports


# --- cache safety -----------------------------------------------------------
def cache_path(slug: str) -> pathlib.Path:
    p = (CACHE_ROOT / f"{slug}.json").resolve()
    # Guardrail: cache must live under ~/.cache, never the vault or a git repo.
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if vault and str(p).startswith(str(pathlib.Path(vault).resolve())):
        raise SystemExit("REFUSING to write Signal cache inside the Obsidian vault.")
    if str(CACHE_ROOT.resolve()) not in str(p):
        raise SystemExit("Cache path escaped CACHE_ROOT — aborting.")
    return p


def write_raw_cache(slug: str, bundle: dict) -> pathlib.Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    p = cache_path(slug)
    payload = {
        "slug": slug,
        "fetched_at": bundle.get("fetched_at"),  # caller stamps; None ok
        "ttl_days": TTL_DAYS,
        "raw": {k: bundle.get(k) for k in ("person", "history", "goals")},
    }
    p.write_text(json.dumps(payload, indent=2))
    return p


# --- normalization ----------------------------------------------------------
def normalize_sentiment(person: dict | None) -> dict:
    if not person:
        return {}
    a = (person.get("analytics") or {}).get("latest") or {}
    return {
        "latest_week": a.get("week_of"),
        "score": a.get("sentiment_score"),
        "score_4w_avg": a.get("sentiment_score_4w_avg"),
        "slope_8w": a.get("sentiment_score_8w_slope"),
        "has_recent_reversal": a.get("has_recent_reversal"),
        "is_novel_low": a.get("is_novel_low"),
        "friction_streak_weeks": a.get("friction_streak_weeks"),
        "streak_just_started": a.get("streak_just_started"),
        "streak_just_broken": a.get("streak_just_broken"),
        "quick_notes_active": (person.get("person") or {}).get("quick_notes_active"),
    }


def normalize_history(history: dict | None) -> dict:
    """Pull wins + friction themes from the structured extraction, screen sensitivity."""
    wins, friction, submitted_weeks, sensitive_dropped = [], [], [], []
    if not history:
        return {"wins": wins, "friction": friction, "submitted_weeks": submitted_weeks,
                "sensitive_dropped": sensitive_dropped}
    for wk in history.get("history", []):
        week = wk.get("week_of")
        if week:
            submitted_weeks.append(week)
        ex = wk.get("extraction") or {}
        for w in ex.get("wins", []):
            desc = w.get("description", "")
            if is_sensitive(desc):
                sensitive_dropped.append({"week": week, "kind": "win", "reason": "sensitivity"})
                continue
            wins.append({"week": week, "text": desc})
        for c in ex.get("challenges", []):
            desc = c.get("description", "")
            if is_sensitive(desc):
                sensitive_dropped.append({"week": week, "kind": "challenge", "reason": "sensitivity"})
                continue
            friction.append({
                "week": week,
                "text": desc,
                "category": c.get("backend_category"),
                "primary_sentiment": wk.get("sentiment_primary"),
            })
    return {"wins": wins, "friction": friction, "submitted_weeks": submitted_weeks,
            "sensitive_dropped": sensitive_dropped}


def normalize_goals(goals: dict | None) -> list[dict]:
    if not goals:
        return []
    out = []
    for g in goals.get("goals", []):
        out.append({
            "name": g.get("goal_name") or g.get("name"),
            "health": g.get("latest_health") or g.get("health"),
            "weeks_since_update": g.get("weeks_since_update"),
            "flagged": g.get("flag_for_discussion") or g.get("flagged"),
        })
    return out


def normalize(slug: str, bundle: dict, weeks: int) -> dict:
    person = bundle.get("person")
    hist = normalize_history(bundle.get("history"))
    return {
        "slug": slug,
        "window_weeks": weeks,
        "fetched_at": bundle.get("fetched_at"),
        "sentiment": normalize_sentiment(person),
        "wins": hist["wins"],
        "friction": hist["friction"],
        "goals": normalize_goals(bundle.get("goals")),
        "submitted_weeks": sorted(set(hist["submitted_weeks"]), reverse=True),
        "sensitive_dropped": hist["sensitive_dropped"],
        # Provenance for the synthesizer: it must apply the KB sensitive-content
        # rubric to the RAW history (read from cache), never paste raw verbatim.
        "raw_cache_path": str(cache_path(slug)),
        "rubric_required": True,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-reports", action="store_true")
    ap.add_argument("--slug")
    ap.add_argument("--weeks", type=int, default=12)
    ap.add_argument("--fetch", action="store_true",
                    help="Token-direct: pull person/history/goals from the Signal API (no MCP, no stdin).")
    ap.add_argument("--team-summary", action="store_true",
                    help="Token-direct: pull the weekly team summary (the manager's team pulse).")
    ap.add_argument("--manager", help="Manager slug for --team-summary (default: token owner).")
    ap.add_argument("--week", help="Friday YYYY-MM-DD for --team-summary (default: most recent).")
    args = ap.parse_args()

    if args.list_reports:
        print(json.dumps(list_reports(), indent=2))
        return

    if args.team_summary:
        print(json.dumps(fetch_team_summary(args.manager, args.week), indent=2))
        return

    if not args.slug:
        raise SystemExit("--slug required (or use --list-reports)")

    if args.fetch:
        bundle = fetch_bundle(args.slug, args.weeks)
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            raise SystemExit("No raw Signal bundle on stdin. Pipe {person,history,goals} JSON, or use --fetch.")
        bundle = json.loads(raw)
    bundle.setdefault("fetched_at", dt.datetime.now(dt.UTC).isoformat())

    p = write_raw_cache(args.slug, bundle)
    log(f"cached raw → {p}")

    norm = normalize(args.slug, bundle, args.weeks)
    log(f"normalized: {len(norm['wins'])} wins, {len(norm['friction'])} friction, "
        f"{len(norm['goals'])} goals, {len(norm['sensitive_dropped'])} sensitive items dropped, "
        f"{len(norm['submitted_weeks'])} weeks submitted")
    print(json.dumps(norm, indent=2))


if __name__ == "__main__":
    main()
