#!/usr/bin/env python3
"""
fetch_airtable_slt.py -- pull all SLT meeting intelligence for one member from Airtable.

Usage:
  python3.12 fetch_airtable_slt.py "Gary Tuerack"
  python3.12 fetch_airtable_slt.py "Adam Stone"

Output: JSON to stdout.  Status messages to stderr.

Requires: AIRTABLE_API_KEY env var.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE_ID = os.environ.get("SLT_BASE_ID", "")
if not BASE_ID:
    print("ERROR: SLT_BASE_ID not set. Copy .env.example to .env and fill in your values.", file=sys.stderr)
    sys.exit(1)
API_BASE = f"https://api.airtable.com/v0/{BASE_ID}"
# LOP tables split to new base 2026-05-01; fall back to SLT_BASE_ID for backwards compat
LOP_BASE_ID = os.environ.get("LOP_BASE_ID", BASE_ID)
LOP_API_BASE = f"https://api.airtable.com/v0/{LOP_BASE_ID}"

# Table IDs — update these to match your Airtable base
TBL_MEMBERS = os.environ.get("SLT_MEMBERS_TABLE", "tbl9GMiujOzOD7xXn")
TBL_COACHING = os.environ.get("SLT_COACHING_TABLE", "tbloYzpUhHBHOuYwr")
TBL_ACTIONS = os.environ.get("SLT_ACTIONS_TABLE", "tblasgjUjadHCqzrg")
TBL_L1_GOALS = os.environ.get("SLT_L1_GOALS_TABLE", "tblFLHHpQUVpLrDjb")
TBL_L2_GOALS = os.environ.get("SLT_L2_GOALS_TABLE", "tblpvFlUEy9GJflzB")
TBL_MEETINGS = os.environ.get("SLT_MEETINGS_TABLE", "tblpPC7Levj9SZEfx")

# Rate limiting: 0.25s between requests (4 req/sec, under 5 req/sec limit)
RATE_DELAY = 0.25
_last_request_time = 0.0


def log(msg: str):
    print(msg, file=sys.stderr)


def get_api_key() -> str:
    key = os.environ.get("AIRTABLE_API_KEY", "")
    if not key:
        log("ERROR: AIRTABLE_API_KEY not set")
        sys.exit(1)
    return key


def airtable_get(table_id: str, params: dict | None = None, base_url: str | None = None) -> list[dict]:
    """Fetch all records from a table, handling pagination.

    Args:
        table_id: Airtable table ID.
        params: Optional query parameters.
        base_url: Override the default API_BASE (use LOP_API_BASE for LOP tables).
    """
    global _last_request_time
    api_key = get_api_key()
    all_records = []
    offset = None
    resolved_base = base_url if base_url else API_BASE

    while True:
        # Rate limiting
        elapsed = time.time() - _last_request_time
        if elapsed < RATE_DELAY:
            time.sleep(RATE_DELAY - elapsed)

        query_params = dict(params or {})
        if offset:
            query_params["offset"] = offset

        url = f"{resolved_base}/{table_id}"
        if query_params:
            url += "?" + urllib.parse.urlencode(query_params, doseq=True)

        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

        _last_request_time = time.time()
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            log(f"ERROR: Airtable API {e.code}: {body[:500]}")
            return all_records

        all_records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break

    return all_records


def fetch_member(person_name: str) -> dict | None:
    """Fetch member record by name. Field is 'member' (not 'Name')."""
    log(f"Fetching member: {person_name}")
    formula = f"{{member}}='{person_name}'"
    records = airtable_get(TBL_MEMBERS, {
        "filterByFormula": formula,
    })
    if not records:
        log(f"ERROR: Member '{person_name}' not found")
        return None
    r = records[0]
    f = r["fields"]
    return {
        "name": f.get("member", ""),
        "role": f.get("role", ""),
        "context_blurb": f.get("context_blurb", ""),
        "email": f.get("email", ""),
        "record_id": r["id"],
        "slack_user_id": f.get("slack_user_id", ""),
        # Linked meeting record IDs (from reverse link on Meetings table)
        "_meeting_ids": f.get("Meetings", []),
    }


def fetch_coaching_feedback(person_name: str) -> list[dict]:
    """Fetch coaching feedback for a member."""
    log(f"Fetching coaching feedback for {person_name}")
    formula = f"{{member_name}}='{person_name}'"
    records = airtable_get(TBL_COACHING, {
        "filterByFormula": formula,
    })
    results = []
    for r in records:
        f = r["fields"]
        meeting_linked = f.get("meeting", [])
        results.append({
            "meeting_date": "",  # enriched later
            "speaking_pct": f.get("speaking_pct"),
            "contribution_quality": f.get("contribution_quality", ""),
            "best_contribution": f.get("best_contribution", ""),
            "start_recommendation": f.get("start_recommendation", ""),
            "stop_recommendation": f.get("stop_recommendation", ""),
            "progress_note": f.get("progress_note", ""),
            "speaking_trend": f.get("speaking_trend", ""),
            "stretch_challenge": f.get("stretch_challenge", ""),
            "_meeting_record_ids": meeting_linked if isinstance(meeting_linked, list) else [],
        })
    log(f"  Found {len(results)} coaching feedback records")
    return results


def fetch_actions(person_name: str) -> list[dict]:
    """Fetch meeting actions assigned to this person via assignee text field."""
    log(f"Fetching actions for {person_name}")
    formula = f"{{assignee}}='{person_name}'"
    records = airtable_get(TBL_ACTIONS, {
        "filterByFormula": formula,
    })
    results = []
    for r in records:
        f = r["fields"]
        topic_tags_raw = f.get("topic_tags", [])
        # due_date and Priority may not exist on all records
        results.append({
            "description": (f.get("action_description", "") or "").strip(),
            "status": f.get("status", ""),
            "due_date": f.get("due_date", ""),
            "priority": f.get("Priority", ""),
            "action_type": f.get("action_type", ""),
            "meeting_date": f.get("meeting_date", [""])[0] if isinstance(f.get("meeting_date"), list) else f.get("meeting_date", ""),
            "topic_tags": topic_tags_raw if isinstance(topic_tags_raw, list) else [],
        })
    log(f"  Found {len(results)} action items")
    return results


def fetch_l1_goals(person_name: str) -> list[dict]:
    """Fetch active L1 goals for 2026 where this person is DRI."""
    log(f"Fetching L1 goals for {person_name}")
    formula = f"AND(FIND('{person_name}', ARRAYJOIN({{User (from DRI)}}, ',')), {{Year}}='2026', {{Active?}}='Active')"
    records = airtable_get(TBL_L1_GOALS, {
        "filterByFormula": formula,
    }, base_url=LOP_API_BASE)
    results = []
    for r in records:
        f = r["fields"]
        results.append({
            "theme": f.get("L1 Theme", ""),
            "smart_goal": f.get("L1 as Smart Goal", ""),
            "active": f.get("Active?", "") == "Active",
            "year": f.get("Year", ""),
        })
    log(f"  Found {len(results)} L1 goals")
    return results


def fetch_l2_goals(person_name: str) -> list[dict]:
    """Fetch active L2 goals for 2026. Full records (no fields[] filter)."""
    log(f"Fetching L2 goals for {person_name}")
    formula = f"AND(FIND('{person_name}', ARRAYJOIN({{User (from DRI)}}, ',')), {{Year}}='2026', {{Status}}='Active')"
    records = airtable_get(TBL_L2_GOALS, {
        "filterByFormula": formula,
    }, base_url=LOP_API_BASE)
    results = []
    for r in records:
        f = r["fields"]
        # Lookup fields return arrays — take [0]
        health_arr = f.get("Latest Update Health", [])
        comment_arr = f.get("Latest update comment", [])
        results.append({
            "goal": f.get("L2 Goals", ""),
            "status": f.get("Status", ""),
            "year": f.get("Year", ""),
            "health": health_arr[0] if isinstance(health_arr, list) and health_arr else (health_arr if isinstance(health_arr, str) else ""),
            "latest_comment": comment_arr[0] if isinstance(comment_arr, list) and comment_arr else (comment_arr if isinstance(comment_arr, str) else ""),
        })
    log(f"  Found {len(results)} L2 goals")
    return results


def fetch_meetings_for_ids(meeting_ids: list[str]) -> list[dict]:
    """Fetch meeting details for a list of meeting record IDs.

    Uses OR(RECORD_ID()='...') formula. Batches if needed (Airtable
    formula length limit ~100KB, each ID ~20 chars, so ~4000 IDs per batch).
    For SLT members we typically have <50 meetings.
    """
    if not meeting_ids:
        return []

    log(f"Fetching {len(meeting_ids)} meetings by record ID")

    # Only fetch meetings from last 12 months to keep output manageable
    # But we need all meetings for coaching date enrichment, so fetch all IDs
    id_parts = [f"RECORD_ID()='{mid}'" for mid in meeting_ids]
    formula = f"OR({','.join(id_parts)})"
    records = airtable_get(TBL_MEETINGS, {
        "filterByFormula": formula,
    })

    results = []
    date_map = {}  # record_id -> formatted date (for coaching enrichment)

    for r in records:
        f = r["fields"]
        date_str = f.get("meeting_date_formatted", "") or f.get("meeting_date", "")
        date_map[r["id"]] = date_str
        results.append({
            "date": f.get("meeting_date", ""),
            "date_formatted": f.get("meeting_date_formatted", ""),
            "title": (f.get("meeting_title", "") or "").strip(),
            "type": f.get("meeting_type", ""),
            "topics": (f.get("_meeting_topics", "") or "").strip(),
            "_record_id": r["id"],
        })

    # Sort by date descending
    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    log(f"  Fetched {len(results)} meeting records")
    return results, date_map


def main():
    if len(sys.argv) < 2:
        print("Usage: python3.12 fetch_airtable_slt.py \"Person Name\"", file=sys.stderr)
        sys.exit(1)

    person_name = sys.argv[1]
    log(f"=== Fetching SLT data for: {person_name} ===")

    # 1. Member lookup
    member = fetch_member(person_name)
    if not member:
        sys.exit(1)

    member_record_id = member["record_id"]
    member_meeting_ids = member.pop("_meeting_ids", [])

    # 2. Fetch all data
    coaching = fetch_coaching_feedback(person_name)
    actions = fetch_actions(person_name)
    l1_goals = fetch_l1_goals(person_name)
    l2_goals = fetch_l2_goals(person_name)

    # 3. Fetch meetings this member is linked to (from Members.Meetings reverse link)
    # Also collect meeting IDs from coaching feedback for date enrichment
    coaching_meeting_ids = set()
    for c in coaching:
        coaching_meeting_ids.update(c.get("_meeting_record_ids", []))

    all_meeting_ids = list(set(member_meeting_ids) | coaching_meeting_ids)
    meetings_list, meeting_date_map = fetch_meetings_for_ids(all_meeting_ids)

    # 4. Enrich coaching feedback with meeting dates
    for c in coaching:
        mids = c.pop("_meeting_record_ids", [])
        if mids:
            c["meeting_date"] = meeting_date_map.get(mids[0], "")
    # Sort coaching by meeting_date descending
    coaching.sort(key=lambda x: x.get("meeting_date", ""), reverse=True)

    # 5. Filter meetings to last 12 months for output and clean up
    cutoff = "2025-03-22"
    meetings_output = []
    for m in meetings_list:
        date_fmt = m.get("date_formatted", "")
        if date_fmt >= cutoff:
            meetings_output.append({
                "date": m["date"],
                "title": m["title"],
                "type": m["type"],
                "topics": m["topics"],
            })

    # 6. Build output
    member_output = {k: v for k, v in member.items() if k != "slack_user_id"}

    output = {
        "member": member_output,
        "coaching_feedback": coaching,
        "actions": actions,
        "l1_goals": l1_goals,
        "l2_goals": l2_goals,
        "meetings_attended": meetings_output,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))
    log("=== Done ===")


if __name__ == "__main__":
    main()
