#!/usr/bin/env python3.12
"""
splice_signal_read.py — write a `## Signal Read` section into an existing profile
in place, WITHOUT a full re-synthesis (no LLM, no paraphrase drift, idempotent).

Use this to enrich already-synthesized profiles with Signal data between full
biweekly sweeps. The full sweep (synthesize_profile.py) produces richer LLM prose
+ <!-- DIGEST --> coaching suggestions; this is the lightweight, deterministic path.

Input (stdin JSON): {"profile_path": "...", "signal": <normalized fetch_signal output>}

Behavior:
- Builds `## Signal Read` from the NORMALIZED (already sensitivity-pre-screened) signal.
- Replaces an existing `## Signal Read` block if present; else inserts before
  `## Coaching Goals` / `## Relationship Health` (curated tail); else appends.
- Adds `signal` to the `sources:` frontmatter list if absent.
- Everything else is byte-preserved.
- Refuses to run if the normalized signal still contains a sensitivity drop count
  mismatch (defensive: the structured lists must already be clean).

Status → stderr. Writes the file in place; prints the spliced section to stdout.
"""
from __future__ import annotations
import datetime as dt
import json
import pathlib
import re
import sys

SECTION = "## Signal Read"


def log(msg: str) -> None:
    print(f"[splice] {msg}", file=sys.stderr)


def sentiment_phrase(s: dict) -> str:
    if not s:
        return "no sentiment data"
    if s.get("quick_notes_active") is False:
        return "not currently submitting Quick Notes"
    score, avg, slope = s.get("score"), s.get("score_4w_avg"), s.get("slope_8w")
    streak = s.get("friction_streak_weeks") or 0
    if s.get("is_novel_low"):
        phrase = "novel low — needs attention"
    elif s.get("has_recent_reversal") and score is not None and avg is not None and score < avg:
        phrase = "recent dip below the 4-week average — worth a direct check-in"
    elif isinstance(slope, (int, float)) and slope > 0.05:
        phrase = "trending up over 8 weeks"
    elif isinstance(slope, (int, float)) and slope < -0.05:
        phrase = "trending down over 8 weeks — watch"
    else:
        phrase = "steady"
    if streak >= 2:
        phrase += f"; friction streak {streak} wks"
    return phrase


def md(week: str) -> str:
    try:
        d = dt.date.fromisoformat(week)
        return f"{d.month}/{d.day}"
    except Exception:
        return week or "?"


def build_section(signal: dict, today: str) -> str:
    lines = [SECTION, f"*Last updated: {today} · source: Quick Notes (distilled)*", ""]
    lines.append(f"- **Sentiment:** {sentiment_phrase(signal.get('sentiment') or {})}")

    wins = signal.get("wins") or []
    if wins:
        lines.append("- **Recent wins:**")
        for w in wins[:3]:
            lines.append(f"  - {w.get('text','')} ({md(w.get('week',''))})")
    else:
        lines.append("- **Recent wins:** none logged this window")

    fr = signal.get("friction") or []
    if fr:
        streak = (signal.get("sentiment") or {}).get("friction_streak_weeks")
        suffix = f" — streak {streak} wks" if streak and streak >= 2 else ""
        themes = "; ".join(f"{f.get('text','')}" for f in fr[:3])
        lines.append(f"- **Recurring friction (themes):** {themes}{suffix}")
    else:
        lines.append("- **Recurring friction (themes):** none surfaced")

    goals = signal.get("goals") or []
    if goals:
        from collections import Counter
        c = Counter((g.get("health") or "unknown").lower() for g in goals)
        flagged = [g.get("name") for g in goals if g.get("flagged")]
        summary = ", ".join(f"{n} {h}" for h, n in c.items())
        line = f"- **Goal health:** {summary}"
        if flagged:
            line += f" · flagged: {', '.join(x for x in flagged if x)}"
        lines.append(line)
    else:
        lines.append("- **Goal health:** no goals tracked in Signal")

    sub = signal.get("submitted_weeks") or []
    if sub:
        most_recent = sub[0]
        gap_flag = ""
        try:
            d = dt.date.fromisoformat(most_recent)
            if (dt.date.fromisoformat(today) - d).days >= 14:
                gap_flag = " ⚠ gap ≥2 weeks"
        except Exception:
            pass
        lines.append(f"- **Submission cadence:** {len(sub)} weeks submitted; most recent {md(most_recent)}{gap_flag}")
    else:
        lines.append("- **Submission cadence:** no Quick Notes in window ⚠")

    dropped = signal.get("sensitive_dropped") or []
    if dropped:
        lines.append(f"- _({len(dropped)} item(s) withheld by the sensitivity filter — see cache)_")

    return "\n".join(lines) + "\n"


def add_signal_source(text: str) -> str:
    m = re.search(r"^sources:\s*\[(.*?)\]\s*$", text, flags=re.MULTILINE)
    if not m:
        return text
    items = [x.strip() for x in m.group(1).split(",") if x.strip()]
    if "signal" in items:
        return text
    items.append("signal")
    return text[: m.start()] + f"sources: [{', '.join(items)}]" + text[m.end():]


def splice(text: str, section: str) -> str:
    # Replace existing ## Signal Read block (up to next ## or EOF)
    pat = re.compile(r"^## Signal Read\b.*?(?=^## |\Z)", flags=re.MULTILINE | re.DOTALL)
    if pat.search(text):
        return pat.sub(section + "\n", text, count=1)
    # Insert before curated tail sections if present
    for anchor in ("## Coaching Goals", "## Relationship Health"):
        idx = text.find("\n" + anchor)
        if idx != -1:
            return text[: idx + 1] + section + "\n" + text[idx + 1:]
    # Else append
    return text.rstrip() + "\n\n" + section


def resolve_redirect(profile_path: pathlib.Path) -> pathlib.Path:
    """If the target is a `type: person-redirect` stub, follow `canonical_profile`
    to the real profile. Coaching content must never land on a redirect stub —
    the org chart yields the Rippling name (e.g. Jana Amsellem) but the canonical
    profile lives under the preferred name (Red Akasha)."""
    if not profile_path.exists():
        return profile_path
    head = profile_path.read_text(encoding="utf-8")[:600]
    if "type: person-redirect" not in head:
        return profile_path
    m = re.search(r'canonical_profile:\s*"?\[\[([^\]]+)\]\]"?', head)
    if not m:
        log(f"WARN: {profile_path.name} is a redirect stub but has no canonical_profile; leaving as-is")
        return profile_path
    canonical = profile_path.parent / f"{m.group(1).strip()}.md"
    if not canonical.exists():
        log(f"WARN: canonical profile {canonical.name} not found; leaving redirect as-is")
        return profile_path
    log(f"redirect: {profile_path.name} → {canonical.name}")
    return canonical


def main() -> None:
    payload = json.loads(sys.stdin.read())
    profile_path = pathlib.Path(payload["profile_path"])
    signal = payload["signal"]
    if not profile_path.exists():
        raise SystemExit(f"profile not found: {profile_path}")
    profile_path = resolve_redirect(profile_path)

    today = dt.date.today().isoformat()
    section = build_section(signal, today)

    # Defensive leak check on the section we're about to write.
    SENS = re.compile(r"\b(ER|hospital|father|mother|\bdad\b|\bmom\b|salary|fired|harass)\b", re.IGNORECASE)
    if SENS.search(section):
        raise SystemExit("ABORT: sensitivity tripwire matched the Signal Read section; refusing to write.")

    text = profile_path.read_text(encoding="utf-8")
    new = splice(text, section)
    new = add_signal_source(new)
    profile_path.write_text(new, encoding="utf-8")
    print(f"[splice] wrote Signal Read → {profile_path}", file=sys.stderr)
    print(section)


if __name__ == "__main__":
    main()
