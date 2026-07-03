#!/usr/bin/env python3
"""
summarize_meeting.py — generate a structured summary of a 1:1 meeting transcript.

Reads JSON from stdin with keys: transcript, title, date, person_name (optional)
Writes JSON line to stdout with keys: date, title, person_name, summary

Status messages go to stderr. Only JSON output goes to stdout.

Requires: ANTHROPIC_API_KEY env var
"""

import json
import os
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parent))
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs

SYSTEM_PROMPT = (
    "You are analyzing NSLS leadership meeting transcripts. "
    "NSLS (National Society of Leadership and Success) is a leadership honor society serving college students. "
    "The user is the meeting host. "
    "You are extracting insights about the other participant for a person intelligence profile."
)

SUMMARY_PROMPT = """Analyze this 1:1 meeting transcript between the user and {person_name}.

Title: {title}
Date: {date}

Transcript:
{transcript}

Write a summary with these sections:

## What {person_name} Focused On
Topics they drove or returned to. What they seem to care most about. Quote them where useful.

## Questions {person_name} Asked
Every substantive question raised. Exact wording where possible.

## {person_name}'s Mental Models
Frameworks, analogies, or thinking patterns they reach for.

## What Energizes Them / What Concerns Them
Two short lists — positive reactions and areas of pause.

## Advice They Gave
Specific recommendations or suggestions.

## Topics Discussed
Bullet list of distinct topics covered (used for project inference).

## Personal Facts
Extract any personal details mentioned in small talk or conversation — family (kids, spouse, parents), hobbies, interests, sports teams, pets, vacations, life events (moving, health, milestones), side projects. Only include facts explicitly stated, not inferences. If no personal details were mentioned, write "None mentioned."

Keep it factual and direct. Preserve their voice."""


def infer_person_name(title):
    """Try to extract a person name from the meeting title."""
    if not title:
        return "the other participant"
    # Common patterns: "Name / User 1:1", "User / Name 1:1", "Name <> User"
    for sep in [" / ", " <> ", " & ", " and ", " - "]:
        if sep in title:
            parts = [p.strip() for p in title.split(sep)]
            for part in parts:
                # Skip the user's name variants
                clean = part.replace("1:1", "").replace("1-on-1", "").strip()
                if clean.lower() not in ("kevin", "kevin prentiss", "kp", ""):
                    return clean
    return "the other participant"


def main():
    # Read JSON from stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        print(f"ERROR: Failed to parse JSON from stdin: {e}", file=sys.stderr)
        sys.exit(1)

    transcript = data.get("transcript", "")
    title = data.get("title", "")
    date = data.get("date", "")
    person_name = data.get("person_name", "") or infer_person_name(title)

    if not transcript:
        print("ERROR: No transcript provided", file=sys.stderr)
        sys.exit(1)

    # Import anthropic SDK
    try:
        import anthropic
    except ImportError:
        print("Installing anthropic...", file=sys.stderr)
        os.system("python3.12 -m pip install anthropic -q")
        import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Truncate transcript to 120k chars
    truncated = transcript[:120_000]
    if len(transcript) > 120_000:
        print(f"WARNING: Transcript truncated from {len(transcript)} to 120000 chars", file=sys.stderr)

    print(f"Summarizing: {title} ({date}) — person: {person_name}", file=sys.stderr)

    prompt = SUMMARY_PROMPT.format(
        person_name=person_name,
        title=title,
        date=date,
        transcript=truncated,
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    summary = message.content[0].text

    # Parse ## Personal Facts section into a structured list
    personal_facts = []
    in_personal_facts = False
    for line in summary.splitlines():
        if line.strip() == "## Personal Facts":
            in_personal_facts = True
            continue
        if in_personal_facts:
            # Stop at the next ## section
            if line.startswith("## "):
                break
            stripped = line.strip().lstrip("- ").strip()
            if stripped and stripped.lower() != "none mentioned.":
                personal_facts.append({"fact": stripped, "date": date})

    result = {
        "date": date,
        "title": title,
        "person_name": person_name,
        "summary": summary,
        "personal_facts": personal_facts,
    }

    print(json.dumps(result), file=sys.stdout)
    print(f"Done. Summary length: {len(summary)} chars, personal facts: {len(personal_facts)}", file=sys.stderr)


if __name__ == "__main__":
    main()
