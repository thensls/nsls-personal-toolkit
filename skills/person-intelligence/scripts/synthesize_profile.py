#!/usr/bin/env python3
"""
synthesize_profile.py — synthesize a person intelligence profile from all available data.

Reads JSON from stdin (person_name + optional sources).
Writes complete Obsidian-ready markdown profile to stdout.
Status messages go to stderr.

Requires: ANTHROPIC_API_KEY env var
"""

import json
import os
import re
import sys
from datetime import date

SYSTEM_PROMPT = (
    "You are building a person intelligence profile for Kevin Prentiss's Obsidian knowledge base. "
    "Kevin is Head of Product & Technology at NSLS (National Society of Leadership and Success). "
    "You synthesize data from multiple sources into a structured profile. "
    "Use direct quotes where available. Be factual and specific — no filler. "
    "Write in a direct, plain-language style. Numbers over adjectives. Short sentences."
)

MAX_PROMPT_CHARS = 100_000


def build_user_prompt(data):
    """Assemble all available data into a structured prompt for Claude."""
    name = data["person_name"]
    sections = []

    sections.append(f"Build a person intelligence profile for **{name}**.")
    sections.append("")

    # --- Meeting summaries ---
    meetings = data.get("meeting_summaries") or []
    if meetings:
        sections.append(f"## Meeting Summaries ({len(meetings)} meetings)")
        for m in meetings:
            sections.append(f"### {m.get('date', 'unknown date')} — {m.get('title', 'untitled')}")
            sections.append(m.get("summary", ""))
            sections.append("")

    # --- SLT Airtable data ---
    slt = data.get("airtable_slt")
    if slt:
        sections.append("## SLT Data (from Airtable)")
        member = slt.get("member") or {}
        if member:
            sections.append(f"- Name: {member.get('name', name)}")
            sections.append(f"- Role: {member.get('role', 'unknown')}")
            if member.get("context_blurb"):
                sections.append(f"- Context: {member['context_blurb']}")

        coaching = slt.get("coaching_feedback") or []
        if coaching:
            sections.append("\n### Coaching Feedback")
            for i, fb in enumerate(coaching, 1):
                sections.append(f"Feedback #{i}:")
                if fb.get("speaking_pct") is not None:
                    sections.append(f"  - Speaking %: {fb['speaking_pct']}")
                if fb.get("contribution_quality"):
                    sections.append(f"  - Contribution quality: {fb['contribution_quality']}")
                if fb.get("best_contribution"):
                    sections.append(f"  - Best contribution: {fb['best_contribution']}")
                if fb.get("start_recommendation"):
                    sections.append(f"  - Start: {fb['start_recommendation']}")
                if fb.get("stop_recommendation"):
                    sections.append(f"  - Stop: {fb['stop_recommendation']}")

        actions = slt.get("actions") or []
        if actions:
            sections.append("\n### Meeting Actions")
            for a in actions:
                status = a.get("status", "")
                sections.append(f"  - [{status}] {a.get('description', '')} (due: {a.get('due_date', 'none')})")

        l1 = slt.get("l1_goals") or []
        if l1:
            sections.append("\n### L1 Goals")
            for g in l1:
                sections.append(f"  - {g}")

        l2 = slt.get("l2_goals") or []
        if l2:
            sections.append("\n### L2 Goals")
            for g in l2:
                sections.append(f"  - {g}")

        attended = slt.get("meetings_attended") or []
        if attended:
            sections.append(f"\n### SLT Meetings Attended ({len(attended)})")
            for mt in attended:
                sections.append(f"  - {mt.get('date', '')} — {mt.get('title', '')} ({mt.get('type', '')})")

    # --- People-ops Airtable data ---
    pops = data.get("airtable_people_ops")
    if pops:
        sections.append("\n## People-Ops Data (from Airtable)")
        emp = pops.get("employee") or {}
        if emp:
            sections.append(f"- Role title: {emp.get('role_title', 'unknown')}")
            sections.append(f"- Department: {emp.get('department', 'unknown')}")
            if emp.get("level"):
                sections.append(f"- Level: {emp['level']}")
            if emp.get("start_date"):
                sections.append(f"- Start date: {emp['start_date']}")

        lop = pops.get("lop_goals") or []
        if lop:
            sections.append("\n### LoP Goals")
            for g in lop:
                sections.append(f"  - {g.get('name', '')} ({g.get('cascade_level', '')}, {g.get('status', '')}): {g.get('description', '')}")

    # --- Existing profiles ---
    existing = data.get("existing_profile")
    if existing:
        sections.append("\n## Existing 30-People Profile (preserve insights not contradicted by new data)")
        sections.append(existing)

    board_profile = data.get("existing_board_profile")
    if board_profile:
        sections.append("\n## Existing Board-Intelligence Profile")
        sections.append(board_profile)

    slt_profile = data.get("existing_slt_profile")
    if slt_profile:
        sections.append("\n## Existing SLT Profile")
        sections.append(slt_profile)

    # --- Projects ---
    projects = data.get("projects") or {}
    confirmed = projects.get("confirmed") or []
    suggested = projects.get("suggested") or []
    if confirmed or suggested:
        sections.append("\n## Project Associations")
        if confirmed:
            sections.append("Confirmed projects:")
            for p in confirmed:
                sections.append(f"  - {p['project']} ({p['matches']} matches): {', '.join(p.get('evidence', []))}")
        if suggested:
            sections.append("Suggested (needs confirmation):")
            for p in suggested:
                sections.append(f"  - {p['project']} ({p['matches']} matches): {', '.join(p.get('evidence', []))}")

    # --- Instructions ---
    sections.append(f"""
---

Now produce the profile for {name} following this exact structure. Output ONLY the markdown content (no frontmatter — I'll add that). Start with `## Role`.

Sections to include (omit any section that has no supporting data):

## Role
One paragraph. What they do, how they relate to Kevin's work.

## What {name} Cares About
Bullet points of recurring themes across all sources. Be specific — cite topics, not vague categories.

## Questions {name} Asks
Use exact quotes in quotation marks where available from meeting summaries. Each bullet is one question.

## Advice and Offers
Specific recommendations, suggestions, or offers they've made. Actionable items.

## Mental Models
Frameworks, analogies, metaphors, and thinking patterns they reach for. Format: "Model name — explanation"

## How to Work With {name}
Practical advice for Kevin based on observed patterns. What works, what to avoid, what they respond to.

## Projects Together
Format each as: `- [[20-projects/project-slug|Project Name]] — their role or contribution`
Use these confirmed projects: {json.dumps([p['project'] for p in confirmed])}
Do NOT include suggested projects in this list.

## Meeting Patterns
Summarize speaking patterns, engagement style, contribution quality trends from coaching feedback if available. Otherwise note meeting frequency and typical topics.

## Meeting History
Format each meeting as: `- [[folder/date|date — title]]`
Use dates and titles from the meeting summaries provided.

Rules:
- Direct quotes in quotation marks where possible
- No filler phrases ("it's worth noting", "importantly", etc.)
- Short sentences
- If a section would have zero content, omit it entirely
- For "Projects Together", only use confirmed projects, not suggested ones
""")

    return "\n".join(sections)


def determine_sources(data):
    """Return list of data source labels that were actually present."""
    sources = []
    if data.get("meeting_summaries"):
        sources.append("fathom-1on1s")
    if data.get("airtable_slt"):
        sources.append("airtable-slt")
    if data.get("airtable_people_ops"):
        sources.append("airtable-people-ops")
    if data.get("existing_profile"):
        sources.append("existing-profile")
    if data.get("existing_board_profile"):
        sources.append("existing-board-profile")
    if data.get("existing_slt_profile"):
        sources.append("existing-slt-profile")
    if data.get("projects"):
        sources.append("project-inference")
    return sources


def determine_role(data):
    """Extract best available role string."""
    slt = data.get("airtable_slt") or {}
    member = slt.get("member") or {}
    if member.get("role"):
        return member["role"]

    pops = data.get("airtable_people_ops") or {}
    emp = pops.get("employee") or {}
    if emp.get("role_title"):
        return emp["role_title"]

    return "NSLS team member"


def determine_tags(data):
    """Build tag list based on available data."""
    tags = ["leadership"]
    slt = data.get("airtable_slt")
    if slt:
        tags.append("slt")
    board = data.get("existing_board_profile")
    if board:
        tags.append("board")
    return tags


def build_context_links(data):
    """Build Obsidian context links for related profiles."""
    name = data["person_name"]
    links = []
    if data.get("existing_slt_profile"):
        slug = name.replace(" ", "-").lower()
        links.append(f"> SLT coaching: [[10-slt/members/{name}]]")
    if data.get("existing_board_profile"):
        links.append(f"> Board profile: [[20-projects/board-intelligence/members/{name}]]")
    return "\n".join(links)


def build_project_comments(data):
    """Build HTML comments for suggested projects."""
    projects = data.get("projects") or {}
    suggested = projects.get("suggested") or []
    comments = []
    for p in suggested:
        evidence = ", ".join(p.get("evidence", []))
        comments.append(f"<!-- SUGGESTED: {p['project']} ({p['matches']} matches: {evidence}) -->")
    return "\n".join(comments)


def count_meetings(data):
    """Count total meetings from all sources."""
    count = len(data.get("meeting_summaries") or [])
    slt = data.get("airtable_slt") or {}
    slt_attended = slt.get("meetings_attended") or []
    # Don't double-count — SLT meetings are a different type
    count += len(slt_attended)
    return count


def build_frontmatter(data):
    """Build YAML frontmatter."""
    name = data["person_name"]
    tags = determine_tags(data)
    role = determine_role(data)
    sources = determine_sources(data)
    meeting_count = count_meetings(data)

    lines = [
        "---",
        "type: person",
        f"tags: [{', '.join(tags)}]",
        f'role: "{role}"',
        "org: NSLS",
        f"last-synthesized: {date.today().isoformat()}",
        f"sources: [{', '.join(sources)}]",
    ]
    if meeting_count > 0:
        lines.append(f"meetings_attended: {meeting_count}")
    lines.append("---")
    return "\n".join(lines)


def postprocess(raw_profile, data):
    """Post-process Claude's output into final Obsidian markdown."""
    name = data["person_name"]
    frontmatter = build_frontmatter(data)
    context_links = build_context_links(data)
    project_comments = build_project_comments(data)

    # Strip any frontmatter Claude might have included
    profile = raw_profile.strip()
    if profile.startswith("---"):
        # Remove Claude's frontmatter
        end = profile.find("---", 3)
        if end != -1:
            profile = profile[end + 3:].strip()

    # Strip leading heading if Claude included `# Name`
    if profile.startswith(f"# {name}"):
        profile = profile[len(f"# {name}"):].strip()

    # Assemble final document
    parts = [frontmatter, "", f"# {name}", ""]

    if context_links:
        parts.append(context_links)
        parts.append("")

    parts.append(profile)

    if project_comments:
        parts.append("")
        parts.append(project_comments)

    result = "\n".join(parts)

    # Ensure file ends with newline
    if not result.endswith("\n"):
        result += "\n"

    return result


def main():
    # Read JSON from stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        print(f"ERROR: Failed to parse JSON from stdin: {e}", file=sys.stderr)
        sys.exit(1)

    person_name = data.get("person_name")
    if not person_name:
        print("ERROR: person_name is required", file=sys.stderr)
        sys.exit(1)

    print(f"Synthesizing profile for: {person_name}", file=sys.stderr)

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

    # Build prompt
    user_prompt = build_user_prompt(data)

    # Truncate if needed
    if len(user_prompt) > MAX_PROMPT_CHARS:
        print(f"WARNING: Prompt truncated from {len(user_prompt)} to {MAX_PROMPT_CHARS} chars", file=sys.stderr)
        user_prompt = user_prompt[:MAX_PROMPT_CHARS]

    sources = determine_sources(data)
    print(f"Data sources: {', '.join(sources) or 'none'}", file=sys.stderr)
    print(f"Prompt length: {len(user_prompt)} chars", file=sys.stderr)
    print("Calling Claude API...", file=sys.stderr)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_profile = message.content[0].text
    print(f"Raw profile: {len(raw_profile)} chars", file=sys.stderr)

    # Post-process
    final = postprocess(raw_profile, data)
    print(f"Final profile: {len(final)} chars", file=sys.stderr)

    # Output to stdout
    print(final, end="")

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
