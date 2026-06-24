#!/usr/bin/env python3
"""assess_biweekly_period.py — produce a real-data-driven health-row assessment
for a single biweekly window.

Takes a person and a 14-day window, fetches the Fathom 1:1 meetings that fell
in that window, summarizes each, and scores the relationship on six dimensions
(Alignment, Trust, Collaboration, Tension, Engagement, Influence Balance) based
on what actually happened. Returns a JSON assessment.

If no meetings happened in the window, returns status="no_data" — the caller
writes an explicit "No 1:1 this period" row rather than carrying forward.

Usage:
    echo '{"person_name": "Adam Stone", "email": "astone@nsls.org",
           "period_start": "2026-04-13"}' | python3.12 assess_biweekly_period.py

Output JSON shape:
    {
      "person_name": "Adam Stone",
      "period_start": "2026-04-13",
      "period_end": "2026-04-27",
      "meetings_count": N,
      "status": "assessed" | "no_data" | "error",
      "alignment": {"emoji": "🟢", "score": 3, "note": "brief evidence"},
      "trust": {...}, "collaboration": {...}, "tension": {...},
      "engagement": {...}, "influence": {...},
      "state": {"emoji": "🟢", "score": 3.0},
      "row_note": "Short row-level note (one phrase)"
    }
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs
CACHE_FILE = Path.home() / ".cache" / "person-intelligence" / ".meeting-cache.json"

# 1-4 scale with emoji mapping
EMOJI_BY_SCORE = {1: "🔴", 2: "🟡", 3: "🟢", 4: "💚"}


def emoji_for(score):
    """Round score to nearest int, return matching emoji."""
    n = max(1, min(4, round(score)))
    return EMOJI_BY_SCORE[n]


SYSTEM_PROMPT = """You are scoring a single biweekly window of one professional relationship.

The user is the operating party in this relationship. You are scoring how the
relationship LOOKED during this specific 14-day window based on meeting
evidence — not the relationship overall.

Six dimensions, 1-4 scale:
- alignment: 1=opposed/diverging, 2=drifting, 3=aligned, 4=highly aligned
- trust: 1=broken, 2=cautious, 3=solid, 4=deep
- collaboration: 1=draining, 2=strained, 3=productive, 4=energizing
- tension: 1=high unresolved friction, 2=some, 3=negligible, 4=none
- engagement: 1=checked out, 2=going through motions, 3=invested, 4=high investment
- influence: 1=heavily one-sided (user dominated or absent), 2=imbalanced, 3=balanced, 4=peak parity

3 is the steady-state default; deviate only with evidence.

Return ONLY JSON in this exact shape:
{
  "alignment": {"score": <1-4>, "note": "<10-20 word evidence>"},
  "trust": {"score": <1-4>, "note": "..."},
  "collaboration": {"score": <1-4>, "note": "..."},
  "tension": {"score": <1-4>, "note": "..."},
  "engagement": {"score": <1-4>, "note": "..."},
  "influence": {"score": <1-4>, "note": "..."},
  "row_note": "<1 short phrase, max 12 words, capturing this period's tone>"
}

Notes must cite specific evidence from the meetings — moments, decisions, quotes —
not generic descriptions. If the data is thin, score 3 (steady state) and say so
in the note. No filler.
"""


def load_meeting_cache():
    """Load the meeting cache directly. Returns list or None."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        return data.get("meetings", [])
    except (json.JSONDecodeError, KeyError):
        return None


def participant_emails(meeting):
    """Extract all invitee emails for a meeting."""
    invitees = meeting.get("calendar_invitees") or []
    emails = []
    for inv in invitees:
        e = inv.get("email") if isinstance(inv, dict) else None
        if e:
            emails.append(e.lower())
    # Also include the recorded_by email
    rb = meeting.get("recorded_by")
    if isinstance(rb, dict) and rb.get("email"):
        emails.append(rb["email"].lower())
    return emails


def fetch_meetings_in_window(email, period_start, period_end):
    """Filter the meeting cache to meetings with `email` as participant in the window.

    Returns (meetings, error). Uses Fathom's pre-computed default_summary directly
    so no Fathom API calls happen.
    """
    cache = load_meeting_cache()
    if cache is None:
        return None, "meeting cache not populated; run fetch_fathom_1on1s.py first"

    target = email.lower()
    matches = []
    for m in cache:
        m_date = (m.get("scheduled_start_time") or m.get("created_at") or "")[:10]
        if not m_date:
            continue
        if m_date < period_start or m_date >= period_end:
            continue
        emails = participant_emails(m)
        if target in emails:
            matches.append(m)
    return matches, None


def extract_summary_text(meeting):
    """Return the best summary text we have, preferring Fathom's pre-computed markdown."""
    ds = meeting.get("default_summary") or {}
    if isinstance(ds, dict):
        md = ds.get("markdown_formatted") or ""
        if md.strip():
            return md
    # Fallback: action items
    items = meeting.get("action_items") or []
    if items:
        return "Action items:\n" + "\n".join(f"- {i}" for i in items if isinstance(i, str))
    return ""


def score_window(person_name, period_start, period_end, summaries):
    """Call Claude to score the 6 dimensions from meeting summaries."""
    try:
        import anthropic
    except ImportError:
        os.system("python3.12 -m pip install anthropic -q")
        import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not set"

    client = anthropic.Anthropic(api_key=api_key)

    user_parts = [
        f"Person: {person_name}",
        f"Window: {period_start} → {period_end}",
        f"Meetings in window: {len(summaries)}",
        "",
    ]
    for i, s in enumerate(summaries, 1):
        user_parts.append(f"--- Meeting {i}: {s.get('date', '?')} — {s.get('title', '')} ---")
        user_parts.append(s.get("summary", ""))
        user_parts.append("")

    user_parts.append("Score this period based on the evidence above. Return only the JSON.")
    user_prompt = "\n".join(user_parts)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:
        return None, f"anthropic call failed: {e}"

    raw = message.content[0].text.strip()
    # Strip any markdown code fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"failed to parse model JSON: {e}; raw: {raw[:300]}"


def build_assessment(scores):
    """From the 6 dimension scores, build the final assessment with emoji."""
    dim_keys = ["alignment", "trust", "collaboration", "tension", "engagement", "influence"]
    result = {}
    score_values = []
    for k in dim_keys:
        v = scores.get(k, {})
        s = v.get("score", 3)
        score_values.append(s)
        result[k] = {"emoji": emoji_for(s), "score": s, "note": v.get("note", "")}
    avg = sum(score_values) / len(score_values) if score_values else 3.0
    result["state"] = {"emoji": emoji_for(avg), "score": round(avg, 2)}
    result["row_note"] = scores.get("row_note", "").strip()
    return result


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "error": f"bad input json: {e}"}))
        sys.exit(1)

    person_name = payload["person_name"]
    email = payload.get("email", "")
    period_start = payload["period_start"]
    period_end_dt = datetime.fromisoformat(period_start).date() + timedelta(days=14)
    period_end = period_end_dt.isoformat()

    print(f"  Assessing {person_name} for {period_start} → {period_end}", file=sys.stderr)

    if not email:
        print(json.dumps({
            "person_name": person_name,
            "period_start": period_start,
            "period_end": period_end,
            "status": "no_email",
            "meetings_count": 0,
        }))
        return

    meetings, err = fetch_meetings_in_window(email, period_start, period_end)
    if err:
        print(json.dumps({
            "person_name": person_name,
            "period_start": period_start,
            "period_end": period_end,
            "status": "error",
            "error": err,
            "meetings_count": 0,
        }))
        return

    print(f"    {len(meetings)} meetings in window", file=sys.stderr)

    if not meetings:
        print(json.dumps({
            "person_name": person_name,
            "period_start": period_start,
            "period_end": period_end,
            "status": "no_data",
            "meetings_count": 0,
        }))
        return

    # Use Fathom's pre-computed default_summary directly — no per-meeting Claude call.
    summaries = []
    for m in meetings:
        summary_text = extract_summary_text(m)
        if not summary_text.strip():
            continue
        summaries.append({
            "date": (m.get("scheduled_start_time") or "")[:10],
            "title": m.get("title", ""),
            "summary": summary_text,
        })

    if not summaries:
        print(json.dumps({
            "person_name": person_name,
            "period_start": period_start,
            "period_end": period_end,
            "status": "error",
            "error": "no summaries available from Fathom for any meeting in window",
            "meetings_count": len(meetings),
        }))
        return

    scores, err = score_window(person_name, period_start, period_end, summaries)
    if err:
        print(json.dumps({
            "person_name": person_name,
            "period_start": period_start,
            "period_end": period_end,
            "status": "error",
            "error": err,
            "meetings_count": len(meetings),
        }))
        return

    assessment = build_assessment(scores)
    assessment.update({
        "person_name": person_name,
        "period_start": period_start,
        "period_end": period_end,
        "status": "assessed",
        "meetings_count": len(meetings),
    })
    json.dump(assessment, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
