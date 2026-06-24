#!/usr/bin/env python3
"""extract_coaching_actions.py — pull actionable coaching items from profiles.

Walks each tracked relationship's Obsidian profile and extracts:

  1. Unchecked `- [ ]` action items from active `## Coaching Goals` sections
  2. Action-shaped lines from the Thrive section's `### Friction to address`
     and `### Growth edges` subsections (the "what to do about it" content)

Each extracted action carries enough context for /open-day to surface it
intelligently: person, relationship_type, text, dimension, priority,
times_surfaced (tracked across runs), status (pending/done/stale/snoozed).

Output: `~/.cache/person-intelligence/coaching_actions.json` keyed by person.

Usage:
    python3.12 extract_coaching_actions.py

Env:
    OPERATING_USER_EMAIL — required
    OBSIDIAN_VAULT_PATH — required
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import resolve_user  # noqa: E402
import list_relationships  # noqa: E402

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "person-intelligence"


def parse_frontmatter(text):
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        lm = re.match(r"^([\w-]+):\s*(.*)$", line)
        if lm:
            fm[lm.group(1)] = lm.group(2).strip().strip('"').strip("'")
    return fm


def health_score(fm):
    try:
        return float(fm.get("health_score", "3.0") or "3.0")
    except (ValueError, TypeError):
        return 3.0


def find_section(text, heading_pattern):
    """Locate a section by heading. Returns (start, end) char offsets or None."""
    m = re.search(heading_pattern, text, re.MULTILINE)
    if not m:
        return None
    start = m.end()
    next_m = re.search(r"^## ", text[start:], re.MULTILINE)
    end = (start + next_m.start()) if next_m else len(text)
    return start, end


def extract_coaching_goal_actions(text):
    """Find unchecked actions in Active coaching goals.

    Returns list of dicts: [{"text": "...", "dimension": "...", "goal_title": "..."}]
    """
    section = find_section(text, r"^## Coaching Goals\s*$")
    if section is None:
        return []
    start, end = section
    section_text = text[start:end]

    # Each active goal looks like:
    #   ### Active: [title]
    #   status: active | created: YYYY-MM-DD | dimension: [dim]
    #   **Why**: ...
    #   **Actions**:
    #   - [ ] action 1
    #   - [ ] action 2
    actions = []
    goal_blocks = re.split(r"^### Active:\s*", section_text, flags=re.MULTILINE)
    for block in goal_blocks[1:]:  # first chunk is pre-first-goal preamble
        title_match = re.match(r"^([^\n]+)", block)
        title = title_match.group(1).strip() if title_match else "Untitled goal"
        # Stop at next ### heading
        next_h = re.search(r"^### ", block, re.MULTILINE)
        block_body = block[: next_h.start()] if next_h else block

        # Dimension
        dim_match = re.search(r"dimension:\s*([^\n|]+)", block_body)
        dimension = dim_match.group(1).strip() if dim_match else None

        # Actions block: after **Actions**: until **Evidence** or end of block
        actions_idx = block_body.find("**Actions**")
        if actions_idx < 0:
            continue
        actions_block = block_body[actions_idx:]
        evidence_idx = actions_block.find("**Evidence**")
        if evidence_idx > 0:
            actions_block = actions_block[:evidence_idx]

        for line in actions_block.split("\n"):
            unchecked = re.match(r"^\s*-\s*\[\s*\]\s*(.+?)\s*$", line)
            if unchecked:
                actions.append({
                    "text": unchecked.group(1).strip(),
                    "dimension": dimension,
                    "goal_title": title,
                    "source": "coaching_goal",
                })
    return actions


def extract_thrive_actions(text):
    """Find action-shaped items in 'What X Needs to Thrive' subsections.

    Friction to address / Growth edges subsections often contain implicit actions
    framed as 'Clear this by...', 'The right support is...', etc. We extract
    lines that look directive — bold-led bullets, sentence-starting verbs.

    Returns list of dicts.
    """
    actions = []
    section = find_section(text, r"^## What [^\n]+ Needs to Thrive\s*$")
    if section is None:
        return []
    start, end = section
    section_text = text[start:end]

    # Split by ### subsection
    for sub_match in re.finditer(
        r"^### (Friction to address|Growth edges)\s*$([\s\S]*?)(?=^###|\Z)",
        section_text,
        re.MULTILINE,
    ):
        subsection = sub_match.group(1)
        body = sub_match.group(2)
        # Look for bold-led bullets like "**Pattern.**" with action language.
        # Heuristic: any bold-led bullet whose body contains an action verb pattern.
        action_verbs = re.compile(
            r"(?i)(?:^|\.\s*)(clear|give|pair|schedule|assign|name|propose|"
            r"surface|reduce|protect|advocate|share|set up|ask|invite|delegate)"
        )
        for bullet_match in re.finditer(
            r"\*\*([^*]+)\*\*\s*([^\n]+(?:\n(?!\*\*|###|##)[^\n]+)*)",
            body,
        ):
            pattern = bullet_match.group(1).strip().rstrip(".")
            body_text = bullet_match.group(2).strip()
            if action_verbs.search(body_text):
                # Extract the actionable sentence — the first sentence with an action verb
                sentences = re.split(r"(?<=[.!?])\s+", body_text)
                action_sentence = next(
                    (s for s in sentences if action_verbs.search(s)),
                    body_text[:200],
                )
                actions.append({
                    "text": f"{pattern}: {action_sentence.strip()}",
                    "dimension": subsection.lower(),
                    "source": "thrive_section",
                })
    return actions


def merge_with_prior_state(new_actions, prior_state, person_name):
    """Carry forward times_surfaced and status from the prior cache.

    Match by (person, text) — exact text match means same action.
    """
    prior_for_person = prior_state.get(person_name, {}).get("actions", [])
    prior_by_text = {a["text"]: a for a in prior_for_person}

    merged = []
    for action in new_actions:
        prior = prior_by_text.get(action["text"])
        if prior:
            action["times_surfaced"] = prior.get("times_surfaced", 0)
            action["status"] = prior.get("status", "pending")
            action["first_seen"] = prior.get("first_seen", date.today().isoformat())
            action["last_surfaced"] = prior.get("last_surfaced")
            action["snooze_until"] = prior.get("snooze_until")
        else:
            action["times_surfaced"] = 0
            action["status"] = "pending"
            action["first_seen"] = date.today().isoformat()
            action["last_surfaced"] = None
            action["snooze_until"] = None
        merged.append(action)

    # Carry forward done/stale/snoozed actions even if they're no longer in the profile
    # (so the digest can show them in "Stale coaching backlog")
    new_texts = {a["text"] for a in new_actions}
    for prior_action in prior_for_person:
        if prior_action["text"] not in new_texts and prior_action.get("status") in {"done", "stale"}:
            merged.append(prior_action)
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT_PATH", ""))
    args = parser.parse_args()

    if not args.vault:
        print("ERROR: OBSIDIAN_VAULT_PATH not set", file=sys.stderr)
        sys.exit(1)
    vault_path = Path(args.vault).expanduser()

    # Get tracked relationship set
    chart_path = resolve_user.find_org_chart()
    if chart_path is None:
        print("ERROR: org-chart.json not found", file=sys.stderr)
        sys.exit(2)
    employees = resolve_user.load_org_chart(chart_path)
    email = resolve_user.get_user_email()
    if not email:
        print("ERROR: OPERATING_USER_EMAIL not set", file=sys.stderr)
        sys.exit(1)
    user = resolve_user.resolve(email, employees)

    tracked = []
    if user:
        for r in user.get("manages", []) or []:
            tracked.append({"name": r, "relationship_type": "direct_report"})
        if user.get("manager"):
            tracked.append({"name": user["manager"], "relationship_type": "manager"})
        if os.environ.get("INCLUDE_MANAGEMENT_PEERS", "").strip() in {"1", "true", "yes"}:
            for peer in list_relationships.find_peers(employees, user.get("manager", "")):
                if peer.get("email", "").lower() != email.lower():
                    tracked.append({"name": peer.get("name", ""), "relationship_type": "peer"})

    for name in list_relationships.parse_key_relationships(os.environ.get("KEY_RELATIONSHIPS", "")):
        if not any(t["name"] == name for t in tracked):
            tracked.append({"name": name, "relationship_type": "key_relationship"})

    # Load prior cache state to carry forward times_surfaced / status
    cache_path = args.cache_dir / "coaching_actions.json"
    prior_state = {}
    if cache_path.exists():
        try:
            prior_state = json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            prior_state = {}

    output = {}
    for t in tracked:
        path = vault_path / "30-people" / f"{t['name']}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        score = health_score(fm)

        coaching_actions = extract_coaching_goal_actions(text)
        thrive_actions = extract_thrive_actions(text)
        all_actions = coaching_actions + thrive_actions

        for a in all_actions:
            a["person"] = t["name"]
            a["relationship_type"] = t["relationship_type"]
            # Priority: lower health score → higher priority. Range 0-100 ish.
            a["priority"] = max(0, int(100 - score * 20))

        merged = merge_with_prior_state(all_actions, prior_state, t["name"])

        output[t["name"]] = {
            "relationship_type": t["relationship_type"],
            "health_score": score,
            "health": fm.get("health"),
            "actions": merged,
        }

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(output, indent=2))

    total_actions = sum(len(v["actions"]) for v in output.values())
    pending = sum(
        1 for v in output.values()
        for a in v["actions"]
        if a.get("status") == "pending"
    )
    stale = sum(
        1 for v in output.values()
        for a in v["actions"]
        if a.get("status") == "stale"
    )
    print(f"Extracted {total_actions} actions ({pending} pending, {stale} stale) across {len(output)} relationships", file=sys.stderr)
    print(f"Written to {cache_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
