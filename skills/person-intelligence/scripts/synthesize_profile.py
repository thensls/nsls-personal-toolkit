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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "references"

SYSTEM_PROMPT_BASE = (
    "You are building a person intelligence profile for the operating user's Obsidian "
    "knowledge base. You synthesize data from multiple sources (Fathom 1:1 transcripts, "
    "Slack/Gmail signal blocks, Airtable employee + SLT data, existing profile content) "
    "into a structured profile. Use direct quotes where available. Be factual and specific — "
    "no filler. Write in a direct, plain-language style: numbers over adjectives, short "
    "sentences, declarative headlines."
)

VALID_RELATIONSHIP_TYPES = ("direct_report", "peer", "manager", "key_relationship")

MAX_PROMPT_CHARS = 100_000

# Section headings the synthesizer is allowed to generate. Anything else
# encountered in an existing profile is treated as human-authored and preserved
# verbatim through extraction + re-injection rather than via LLM instruction.
STANDARD_SECTION_HEADINGS = {
    "Role",
    "Core Identity & Self-Concept",
    "Leadership Style",
    "Mental Models",
    "Mental Models (Recurring)",
    "Strategic Priorities",
    "What Energizes Them",
    "What Energizes Him",
    "What Energizes Her",
    "What Concerns Them",
    "What Concerns Him",
    "What Concerns Her",
    "How They Manage Up / Down / Laterally",
    "How He Manages Up / Down / Laterally",
    "How She Manages Up / Down / Laterally",
    "How to Work With",
    "Personal Practices & Interests",
    "Communication Patterns",
    "Key Relationships",
    "Key Relationships (Their Lens)",
    "Key Relationships (His Lens)",
    "Key Relationships (Her Lens)",
    "Quotes That Capture Them",
    "Quotes That Capture Him",
    "Quotes That Capture Her",
    # Coaching frames produced by the synthesizer per relationship_type:
    "What",  # matches "What [Name] Needs to Thrive"
    "How I Work with",  # matches "How I Work with [Name]"
    "My Stance",  # matches "My Stance: ..."
    "How I Can Work More Effectively with",
    "Working Pattern",
    # Standard tail sections:
    "Projects Together",
    "Meeting Patterns",
    "Meeting History",
    "Personal",
    "Signal Read",  # regenerated each run from distilled Quick Notes signal
    # Note: "Coaching Goals" and "Relationship Health" are NOT in this list.
    # They contain user-curated runtime data (active goals, the emoji chart,
    # journal entries) and must be preserved verbatim like human-authored sections.
}


def extract_human_authored_sections(existing_profile):
    """Parse `## ...` sections from existing_profile, return those whose heading
    is NOT in STANDARD_SECTION_HEADINGS.

    Returns list of dicts: [{"heading": "## Kevin's Stance: ...", "content": "..."}, ...]
    Content includes the heading line and everything until the next `## ` heading
    or end of document.
    """
    if not existing_profile:
        return []

    # Split on `## ` headings while keeping the heading text
    parts = re.split(r"(^## .+$)", existing_profile, flags=re.MULTILINE)
    # parts is interleaved: [pre-text, heading1, body1, heading2, body2, ...]
    sections = []
    i = 1
    while i < len(parts):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        # Extract heading text after `## `
        heading_text = heading.lstrip("#").strip()
        # Match against known standard headings (allow prefix-match for templated ones like "What X Needs to Thrive")
        is_standard = any(
            heading_text == std or heading_text.startswith(std + " ") or heading_text.startswith(std + ":")
            for std in STANDARD_SECTION_HEADINGS
        )
        if not is_standard:
            sections.append({
                "heading": heading,
                "content": heading + body,
            })
        i += 2
    return sections


def load_reference(filename):
    """Load a reference frame file, return its content or empty string if missing."""
    path = REFERENCES_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_system_prompt(relationship_type):
    """Compose the system prompt: base + dimensional discovery + conditional frame."""
    parts = [SYSTEM_PROMPT_BASE]

    # Always-on: dimensional discovery
    discovery = load_reference("dimensional-discovery-frame.md")
    if discovery:
        parts.append("\n\n--- DIMENSIONAL DISCOVERY (always applied) ---\n")
        parts.append(discovery)

    # Conditional: relationship-type-specific frame
    frame_file = {
        "direct_report": "manager-coaching-frame.md",
        "manager": "manager-relationship-frame.md",
    }.get(relationship_type)
    if frame_file:
        frame = load_reference(frame_file)
        if frame:
            parts.append(f"\n\n--- RELATIONSHIP FRAME ({relationship_type}) ---\n")
            parts.append(frame)

    return "".join(parts)


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

    # --- Signal (Quick Notes) — distilled, pre-screened for sensitivity ---
    # Phase 1: only the NORMALIZED signal reaches the prompt. Raw weekly narration
    # stays cache-only (fetch_signal.py already dropped HR/health/comp items). The
    # synthesizer must still apply the KB sensitive-content rubric: write only
    # shareable facts, never paste a quote that names comp/health/personnel status.
    signal = data.get("signal")
    if signal:
        sections.append("\n## Signal — Quick Notes (distilled; apply the sensitive-content rubric)")
        s = signal.get("sentiment") or {}
        if s:
            sections.append(
                f"- Sentiment: latest score {s.get('score')} (4w avg {s.get('score_4w_avg')}, "
                f"8w slope {s.get('slope_8w')}); reversal={s.get('has_recent_reversal')}, "
                f"novel_low={s.get('is_novel_low')}, friction_streak_weeks={s.get('friction_streak_weeks')}, "
                f"quick_notes_active={s.get('quick_notes_active')}"
            )
        wins = signal.get("wins") or []
        if wins:
            sections.append("- Recent wins (shareable):")
            for w in wins[:8]:
                sections.append(f"  - [{w.get('week','')}] {w.get('text','')}")
        fr = signal.get("friction") or []
        if fr:
            sections.append("- Recurring friction (themes — de-personalize if sensitive):")
            for f in fr[:8]:
                sections.append(f"  - [{f.get('week','')}] {f.get('text','')} ({f.get('category','')})")
        goals = signal.get("goals") or []
        if goals:
            sections.append("- Goal health:")
            for g in goals[:8]:
                sections.append(f"  - {g.get('name','')}: {g.get('health','')} "
                                f"(updated {g.get('weeks_since_update','?')}w ago"
                                f"{', FLAGGED' if g.get('flagged') else ''})")
        sub = signal.get("submitted_weeks") or []
        if sub:
            sections.append(f"- Submission cadence: {len(sub)} weeks submitted; most recent {sub[0]}")
        dropped = signal.get("sensitive_dropped") or []
        if dropped:
            sections.append(f"- ({len(dropped)} item(s) withheld by the sensitivity pre-filter — do not attempt to recover them)")
        sections.append(
            "\nUsing ONLY the distilled signal above, produce a `## Signal Read` section with these lines:\n"
            "- **Sentiment:** trajectory in plain words (e.g. 'steady; dipped wk of X, recovered'). No raw score dump.\n"
            "- **Recent wins:** 1-3, named + week.\n"
            "- **Recurring friction (themes):** theme + streak weeks; de-personalize anything sensitive.\n"
            "- **Goal health:** counts + any flagged.\n"
            "- **Submission cadence:** weekly, or a gap of N weeks.\n"
            "Then, if the signal shows evidence relevant to an ACTIVE coaching goal, emit a "
            "`<!-- DIGEST: Signal evidence for [goal] — [observation] -->` comment so the biweekly "
            "review can surface it for approval. NEVER write directly into Coaching Goals; it is "
            "user-curated. NEVER include comp, health, family, or personnel-status content."
        )

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

    # --- Existing profile preservation instruction ---
    existing = data.get("existing_profile")
    relationship_type = data.get("relationship_type", "peer")
    human_sections = extract_human_authored_sections(existing) if existing else []
    if human_sections:
        sections.append(
            "\n## Human-authored sections — DO NOT GENERATE\n"
            "The user has manually curated these sections in the existing profile. "
            "**Do NOT include them in your output.** Python post-processing will re-inject "
            "them at the correct position after your synthesis runs. If you wrote them, "
            "they would get duplicated.\n"
            "\nSections to skip generating:"
        )
        for s in human_sections:
            sections.append(f"  - {s['heading']}")
        sections.append(
            "\nIf you have observations from recent data that suggest these sections need "
            "updating, mention them as `<!-- DIGEST: ... -->` comments in your output. "
            "The digest review step will surface them to the user."
        )

    # --- Confirmed projects list ---
    confirmed_list = [p['project'] for p in confirmed]

    # --- Final instructions ---
    sections.append(f"""
---

Now produce the profile for {name}. Output ONLY the markdown body (no frontmatter — that's added in post-processing). Start with `## Core Identity & Self-Concept` (or whichever first section the data supports).

Relationship type for this person: **{relationship_type}**

## Standard section structure (omit any section without supporting data)

1. `## Core Identity & Self-Concept` — How they frame themselves and the work. Direct quotes where available.
2. `## Leadership Style` — 2-5 bold-lead patterns with evidence.
3. `## Mental Models (Recurring)` — Table format. `| Model | How They Use It |`
4. `## Strategic Priorities` — bold-lead paragraphs per priority with quotes and evidence.
5. `## What Energizes Them` — bullets.
6. `## What Concerns Them` — bullets.
7. `## How They Manage Up / Down / Laterally` — paragraphs.
8. `## Personal Practices & Interests` — bullets.
9. `## Communication Patterns` — bold-lead bullets.
10. `## Key Relationships (Their Lens)` — table format if 3+ relationships, otherwise prose.
11. `## Quotes That Capture Them` — block quotes with context.
12. **[Conditional coaching sections per relationship_type — see RELATIONSHIP FRAME in system prompt]**
13. `## Projects Together` — confirmed only: {json.dumps(confirmed_list)}
14. `## Personal` — family/interests/life events bullets, with Last updated date.
15. `## Signal Read` — ONLY if a Signal block was provided above. Follow the line structure in that block. Distilled facts only; apply the sensitive-content rubric.

## Conditional sections (based on relationship_type)

- If `direct_report`: add `## What {name} Needs to Thrive` and `## How I Work with {name}` after section 11. See the manager-coaching frame in the system prompt for subsection structure.
- If `manager`: add `## My Stance: [emotions]` and `## How I Can Work More Effectively with {name}` after section 11. See the manager-relationship frame in the system prompt for structure.
- If `peer` or `key_relationship`: skip coaching sections; replace with `## Working Pattern` (one paragraph or short bullets).

## Hard rules

- **Apply the DIMENSIONAL DISCOVERY instruction in the system prompt before writing.** Find the dimensions specific to this person before fitting to template.
- Direct quotes in quotation marks where possible
- No filler phrases ("it's worth noting", "importantly", "additionally", etc.)
- Short sentences, declarative headlines
- Omit any section that would have zero content — do not pad
- For "Projects Together", only use confirmed projects, not suggested ones
- If the existing profile has human-authored sections (see above), include them verbatim in your output
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
    if data.get("signal"):
        sources.append("signal")
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


def _existing_fm_value(data, key):
    """Return a frontmatter scalar from the existing profile, or None.

    Health scores (`health`, `health_score`, `health_last_assessed`) and the
    `health-*` graph tag are set by the relationship-health-check flow, NOT by
    synthesis. Synthesis rebuilds frontmatter from scratch, so it must carry these
    forward verbatim — otherwise every re-synthesis silently wipes the health
    dashboard while leaving the body health table intact.
    """
    text = data.get("existing_profile") or ""
    m = re.search(rf"^{re.escape(key)}:[ \t]*(\S[^\n]*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def determine_tags(data):
    """Build tag list based on available data."""
    tags = ["leadership"]
    slt = data.get("airtable_slt")
    if slt:
        tags.append("slt")
    board = data.get("existing_board_profile")
    if board:
        tags.append("board")
    # Preserve the health-* graph-coloring tag set by the health-check flow.
    for t in re.findall(r"health-[a-z]+", _existing_fm_value(data, "tags") or ""):
        if t not in tags:
            tags.append(t)
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
    # Carry forward health-dashboard fields owned by the health-check flow.
    for hk in ("health", "health_score", "health_last_assessed"):
        hv = _existing_fm_value(data, hk)
        if hv is not None:
            lines.append(f"{hk}: {hv}")
    if meeting_count > 0:
        lines.append(f"meetings_attended: {meeting_count}")
    lines.append("---")
    return "\n".join(lines)


def reinject_human_sections(profile, human_sections):
    """Re-insert human-authored sections into the synthesized profile.

    Strategy: insert preserved sections just before the first "tail" section
    (Coaching Goals, Relationship Health, or the standalone Personal section
    — not Personal Practices, which is mid-document).
    """
    if not human_sections:
        return profile

    # Use exact heading matching via regex to avoid prefix collisions like
    # "## Personal" vs "## Personal Practices & Interests".
    tail_pattern = re.compile(
        r"^## (Coaching Goals|Relationship Health|Personal)\s*$",
        re.MULTILINE,
    )
    m = tail_pattern.search(profile)
    insertion_point = m.start() if m else -1

    preserved_block = "\n\n".join(s["content"].rstrip() for s in human_sections)

    if insertion_point == -1:
        # No tail section found — append to end.
        return profile.rstrip() + "\n\n" + preserved_block + "\n"

    # Insert preserved block just before the first tail section.
    return profile[:insertion_point].rstrip() + "\n\n" + preserved_block + "\n\n" + profile[insertion_point:]


# Semantic-overlap keywords for coaching artifacts. If a preserved section's
# heading contains one of these, and the LLM also wrote a section whose heading
# contains the same keyword, prefer the preserved one and drop the LLM's.
SEMANTIC_OVERLAP_KEYWORDS = (
    "Stance",
    "Needs to Thrive",
    "How I Work with",
    "How I Can Work",
    "Guardrail",
    "Working Pattern",
)


def find_overlap_keyword(heading):
    """Return the first overlap keyword found in heading, or None."""
    for kw in SEMANTIC_OVERLAP_KEYWORDS:
        if kw.lower() in heading.lower():
            return kw
    return None


def remove_overlapping_llm_sections(profile, human_sections):
    """For each preserved section whose heading hits a known coaching artifact,
    remove any LLM-generated section whose heading hits the same keyword.

    Example: preserved "## Kevin's Stance: ..." → drop LLM's "## My Stance: ...".
    """
    # Build set of overlap keywords claimed by preserved sections.
    preserved_keywords = set()
    for s in human_sections:
        kw = find_overlap_keyword(s["heading"])
        if kw:
            preserved_keywords.add(kw)

    if not preserved_keywords:
        return profile

    # Walk the profile, identify each section, drop those whose heading
    # contains a preserved keyword.
    parts = re.split(r"(^## .+$)", profile, flags=re.MULTILINE)
    out = [parts[0]]
    i = 1
    while i < len(parts):
        heading = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        kw = find_overlap_keyword(heading)
        if kw and kw in preserved_keywords:
            # Skip this LLM section; preserved version will replace it.
            pass
        else:
            out.append(heading)
            out.append(body)
        i += 2
    return "".join(out)


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

    # Re-inject human-authored sections extracted from existing profile.
    human_sections = extract_human_authored_sections(data.get("existing_profile", ""))
    if human_sections:
        # Step 1: remove any LLM-generated section that semantically overlaps
        # with a preserved one (e.g., LLM's "## My Stance" when "## Kevin's Stance"
        # is preserved).
        profile = remove_overlapping_llm_sections(profile, human_sections)

        # Step 2: also remove exact-heading duplicates the LLM may have written.
        for s in human_sections:
            heading_line = s["heading"]
            if heading_line in profile:
                start = profile.find(heading_line)
                next_heading_pattern = re.compile(r"\n## ", re.MULTILINE)
                m = next_heading_pattern.search(profile, start + len(heading_line))
                end = m.start() + 1 if m else len(profile)
                profile = profile[:start].rstrip() + "\n" + profile[end:]

        # Step 3: re-insert preserved sections at the tail position.
        profile = reinject_human_sections(profile, human_sections)

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

    # Validate relationship_type (default: peer for safety — no coaching content)
    relationship_type = data.get("relationship_type", "peer")
    if relationship_type not in VALID_RELATIONSHIP_TYPES:
        print(
            f"WARN: invalid relationship_type {relationship_type!r}, defaulting to 'peer'. "
            f"Valid values: {VALID_RELATIONSHIP_TYPES}",
            file=sys.stderr,
        )
        relationship_type = "peer"
        data["relationship_type"] = "peer"

    print(f"Synthesizing profile for: {person_name} (type: {relationship_type})", file=sys.stderr)

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

    system_prompt = build_system_prompt(relationship_type)
    print(f"System prompt: {len(system_prompt)} chars", file=sys.stderr)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=system_prompt,
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
