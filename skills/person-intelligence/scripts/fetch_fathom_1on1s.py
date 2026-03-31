#!/usr/bin/env python3
"""
fetch_fathom_1on1s.py -- pull 1:1 meeting transcripts from Fathom for any person.

Generalizes ~/board-kb/scripts/fetch_fathom.py to work with any email(s).

Usage:
  python3.12 fetch_fathom_1on1s.py --email a@x.com --list
  python3.12 fetch_fathom_1on1s.py --email a@x.com --email b@x.com --list
  python3.12 fetch_fathom_1on1s.py --email a@x.com --fetch-all
  python3.12 fetch_fathom_1on1s.py --email a@x.com --date 2025-12-03
  python3.12 fetch_fathom_1on1s.py --email a@x.com --exclude-title "all staff" --list
  python3.12 fetch_fathom_1on1s.py --email a@x.com --after 2025-01-01 --fetch-all

Output: JSON lines to stdout (one JSON object per meeting).
Status/progress messages go to stderr.

Requires: FATHOM_API_KEY env var (or set in ~/nsls-skills/slt-ops/slt-bot/.env)
Requires: pip install httpx
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

FATHOM_BASE = "https://api.fathom.ai/external/v1"
MEETINGS_URL_BASE = (
    f"{FATHOM_BASE}/meetings"
    "?calendar_invitees_domains_type=all"
    "&include_action_items=true"
    "&include_summary=true"
)


def build_meetings_url(after_date: str | None = None, before_date: str | None = None) -> str:
    """Build Fathom meetings URL with date-scoped params.

    When dates are provided, uses created_after/created_before API params
    to avoid paginating through all meetings since 2023.
    """
    url = MEETINGS_URL_BASE
    if after_date:
        url += f"&created_after={after_date}T00:00:00Z"
    else:
        url += "&created_after=2023-01-01"
    if before_date:
        url += f"&created_before={before_date}T23:59:59Z"
    return url

CACHE_DIR = Path.home() / ".cache" / "person-intelligence"
CACHE_FILE = CACHE_DIR / ".meeting-cache.json"
CACHE_MAX_AGE_HOURS = 6


def get_api_key() -> str:
    key = os.environ.get("FATHOM_API_KEY", "")
    if not key:
        env_file = Path.home() / "nsls-skills/slt-ops/slt-bot/.env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("FATHOM_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not key:
        print("ERROR: FATHOM_API_KEY not set.", file=sys.stderr)
        print("  Export it: export FATHOM_API_KEY=your_key", file=sys.stderr)
        sys.exit(1)
    return key


def load_cached_meetings() -> list[dict] | None:
    """Return cached meetings if cache is fresh, else None."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            print(
                f"  Using cached meeting list ({len(data['meetings'])} meetings, {age_hours:.1f}h old)",
                file=sys.stderr,
            )
            return data["meetings"]
    except Exception:
        pass
    return None


def save_cached_meetings(meetings: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(
            {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "meetings": meetings,
            }
        )
    )


def fetch_all_meetings(api_key: str, after_date: str | None = None, before_date: str | None = None) -> list[dict]:
    """Fetch meetings from Fathom (paginated, with retry on 429).

    When after_date/before_date are provided, the API call is date-scoped
    to avoid paginating through all meetings since 2023.
    """
    headers = {"X-Api-Key": api_key}
    meetings = []
    url = build_meetings_url(after_date, before_date)
    cursor = None
    page = 0

    while True:
        page += 1
        page_url = url + (f"&cursor={cursor}" if cursor else "")

        # Retry up to 3 times on rate limit
        for attempt in range(3):
            resp = httpx.get(page_url, headers=headers, timeout=30)
            if resp.status_code == 429:
                wait = 2**attempt * 3  # 3s, 6s, 12s
                print(
                    f"  Rate limited (page {page}), waiting {wait}s...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break

        data = resp.json()
        items = data.get("items") or (data if isinstance(data, list) else [])
        meetings.extend(items)
        print(
            f"  Page {page}: {len(items)} meetings (total so far: {len(meetings)})",
            file=sys.stderr,
        )

        cursor = data.get("next_cursor") if isinstance(data, dict) else None
        if not cursor:
            break

        time.sleep(1)  # polite pause between pages

    save_cached_meetings(meetings)
    return meetings


def fetch_all_meetings_cached(api_key: str, after_date: str | None = None, before_date: str | None = None) -> list[dict]:
    # Only use cache for full (unscoped) fetches
    if not after_date and not before_date:
        cached = load_cached_meetings()
        if cached is not None:
            return cached
    return fetch_all_meetings(api_key, after_date, before_date)


def fetch_transcript(api_key: str, recording_id) -> list[dict]:
    """Fetch raw transcript segments for a recording."""
    url = f"{FATHOM_BASE}/recordings/{recording_id}/transcript"
    headers = {"X-Api-Key": api_key}

    for attempt in range(3):
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 429:
            wait = 2**attempt * 3
            print(
                f"  Rate limited (transcript), waiting {wait}s...", file=sys.stderr
            )
            time.sleep(wait)
            continue
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        break

    data = resp.json()
    if isinstance(data, list):
        return data
    return data.get("transcript") or data.get("items") or []


def format_timestamp(ts) -> str:
    if not ts:
        return "00:00:00"
    if isinstance(ts, str):
        return ts
    if isinstance(ts, (int, float)) and ts > 100000:
        ts = ts / 1000
    total = int(float(ts))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def format_transcript(segments: list[dict]) -> str:
    """Format transcript segments into readable text with speaker merging."""
    lines = []
    prev_speaker = None
    current_texts = []
    current_ts = None

    for seg in segments:
        speaker_info = seg.get("speaker", {})
        speaker = (
            speaker_info
            if isinstance(speaker_info, str)
            else speaker_info.get("display_name", "Unknown")
        )
        text = seg.get("text", "").strip()
        if not text:
            continue
        ts = format_timestamp(seg.get("timestamp", 0))
        if speaker == prev_speaker:
            current_texts.append(text)
        else:
            if prev_speaker and current_texts:
                lines.append(f"[{current_ts}] {prev_speaker}:")
                lines.append(" ".join(current_texts))
                lines.append("")
            prev_speaker = speaker
            current_texts = [text]
            current_ts = ts

    if prev_speaker and current_texts:
        lines.append(f"[{current_ts}] {prev_speaker}:")
        lines.append(" ".join(current_texts))
        lines.append("")

    return "\n".join(lines)


def is_1on1_match(
    meeting: dict, emails: set[str], exclude_title_tokens: list[str]
) -> bool:
    """Check if meeting includes target person and isn't excluded by title."""
    invitees = meeting.get("calendar_invitees") or []
    invitee_emails = {(inv.get("email") or "").lower().strip() for inv in invitees}
    if not invitee_emails.intersection(emails):
        return False
    title = (meeting.get("title") or "").lower().strip()
    for token in exclude_title_tokens:
        if token.lower() in title:
            return False
    return True


def meeting_to_jsonl(meeting: dict, transcript_text: str) -> dict:
    """Build the JSON-lines output dict for a meeting."""
    start = meeting.get("scheduled_start_time") or ""
    date_str = start[:10] if start else "unknown-date"
    title = meeting.get("title", "")
    summary_data = meeting.get("default_summary") or {}
    invitees = meeting.get("calendar_invitees") or []

    return {
        "date": date_str,
        "title": title,
        "attendees": [
            inv.get("name") or inv.get("email", "") for inv in invitees
        ],
        "fathom_summary": summary_data.get("markdown_formatted", ""),
        "action_items": [
            a.get("description", "") for a in (meeting.get("action_items") or [])
        ],
        "transcript": transcript_text,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch 1:1 meeting transcripts from Fathom for any person"
    )
    parser.add_argument(
        "--email",
        action="append",
        required=True,
        help="Email address of the person (repeatable for multiple emails)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List matching meetings to stderr (no stdout output unless combined with --fetch-all)",
    )
    parser.add_argument(
        "--fetch-all",
        action="store_true",
        help="Fetch transcripts for all matches, output JSON lines to stdout",
    )
    parser.add_argument(
        "--date", help="Fetch one specific meeting by date YYYY-MM-DD"
    )
    parser.add_argument(
        "--exclude-title",
        action="append",
        default=[],
        help="Exclude meetings with this token in title (repeatable, case-insensitive)",
    )
    parser.add_argument(
        "--after",
        help="Only return meetings on or after YYYY-MM-DD",
    )
    args = parser.parse_args()

    emails = {e.lower().strip() for e in args.email}
    exclude_tokens = args.exclude_title

    if not args.list and not args.fetch_all and not args.date:
        parser.print_help()
        sys.exit(1)

    api_key = get_api_key()

    # Scope API call by date when possible to avoid full pagination
    api_after = args.after if args.after else None
    api_before = None
    if args.date:
        # Single day: scope API to just that day
        api_after = args.date
        from datetime import date as date_type, timedelta
        api_before = (date_type.fromisoformat(args.date) + timedelta(days=1)).isoformat()

    print("Fetching meetings from Fathom...", file=sys.stderr)
    all_meetings = fetch_all_meetings_cached(api_key, after_date=api_after, before_date=api_before)
    print(f"Total meetings returned: {len(all_meetings)}", file=sys.stderr)

    # Filter to 1:1s with this person
    meetings = [
        m for m in all_meetings if is_1on1_match(m, emails, exclude_tokens)
    ]

    # Apply --after filter (client-side, in case API doesn't support exact date matching)
    if args.after:
        meetings = [
            m
            for m in meetings
            if (m.get("scheduled_start_time") or "")[:10] >= args.after
        ]

    # Sort by date
    meetings.sort(key=lambda x: x.get("scheduled_start_time", ""))

    if args.list and not args.fetch_all and not args.date:
        # List-only mode: human-readable to stderr, nothing to stdout
        if not meetings:
            print("No matching meetings found.", file=sys.stderr)
            return
        print(
            f"\nFound {len(meetings)} matching meeting(s):\n", file=sys.stderr
        )
        for m in meetings:
            start = (m.get("scheduled_start_time") or "")[:10]
            title = m.get("title", "")
            rid = m.get("recording_id", "?")
            print(
                f"  {start}  |  {title}  |  recording_id={rid}",
                file=sys.stderr,
            )
        return

    if args.date:
        # Single meeting by date
        match = None
        for m in meetings:
            start = (m.get("scheduled_start_time") or "")[:10]
            if start == args.date:
                match = m
                break
        if not match:
            print(f"No matching meeting found for {args.date}.", file=sys.stderr)
            sys.exit(1)

        rid = match.get("recording_id")
        print(
            f"Fetching transcript for {args.date}: {match.get('title')}",
            file=sys.stderr,
        )
        segments = fetch_transcript(api_key, rid) if rid else []
        transcript_text = format_transcript(segments)
        record = meeting_to_jsonl(match, transcript_text)
        print(json.dumps(record))
        return

    if args.fetch_all:
        # Fetch all matching meetings
        if args.list:
            print(
                f"\nFound {len(meetings)} matching meeting(s), fetching all...\n",
                file=sys.stderr,
            )
        for m in meetings:
            rid = m.get("recording_id")
            date_str = (m.get("scheduled_start_time") or "")[:10]
            title = m.get("title", "")
            print(f"  Fetching: {date_str} | {title}", file=sys.stderr)
            segments = fetch_transcript(api_key, rid) if rid else []
            transcript_text = format_transcript(segments)
            record = meeting_to_jsonl(m, transcript_text)
            print(json.dumps(record))
            time.sleep(0.5)  # polite between transcript fetches
        print(f"\nDone. Output {len(meetings)} meetings.", file=sys.stderr)
        return


if __name__ == "__main__":
    main()
