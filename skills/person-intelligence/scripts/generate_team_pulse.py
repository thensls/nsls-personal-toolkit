#!/usr/bin/env python3
"""generate_team_pulse.py — produce a biweekly cross-relational digest.

Reads the most recent biweekly_sweep manifest + each tracked profile's
frontmatter (health, last-synthesized) + the most recent journal entry,
assembles structured input, and produces a team-pulse markdown digest via
a single Claude API call.

The digest is the cross-relational layer — patterns ACROSS the team rather
than per-profile. Per-profile updates live in each `30-people/[Name].md`.

Usage:
    python3.12 generate_team_pulse.py [--manifest PATH] [--dry-run]

Env:
    ANTHROPIC_API_KEY — required
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
import load_dotenv_local  # noqa: E402,F401  — load .env into os.environ for cron/non-interactive runs
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "person-intelligence"

SYSTEM_PROMPT = """You are producing a biweekly team-pulse digest for a manager.
The audience is the operating user reviewing their own team relationships.

Tone: terse, plain language, declarative headlines. No corporate-speak
(leverage, synergies, robust, learnings, alignment-as-verb). Numbers and
quotes over adjectives. Short sentences.

Each section should only appear if the data supports it. Skip empty sections.
"Cadence Integrity" always renders.

Format the output as Obsidian-flavored markdown. Use the template structure
provided. Do NOT include YAML frontmatter — the caller adds that.
"""


def parse_frontmatter(text):
    """Return dict of frontmatter fields."""
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        line_match = re.match(r"^([\w-]+):\s*(.*)$", line)
        if line_match:
            key = line_match.group(1)
            value = line_match.group(2).strip().strip('"').strip("'")
            fm[key] = value
    return fm


def latest_journal_entry(profile_text, max_chars=1200):
    """Extract the most recent journal entry (after ## Relationship Health header).

    Returns the entry text or None.
    """
    # Find first ### YYYY-MM-DD header after ## Relationship Health
    m = re.search(r"^## Relationship Health\s*$", profile_text, re.MULTILINE)
    if not m:
        return None
    after = profile_text[m.end():]
    entry_match = re.search(r"^### (\d{4}-\d{2}-\d{2})[^\n]*\n", after, re.MULTILINE)
    if not entry_match:
        return None
    entry_start = entry_match.start()
    # End at the next ### heading or end of file
    next_entry = re.search(r"^### \d{4}-\d{2}-\d{2}", after[entry_start + 4:], re.MULTILINE)
    entry_end = (entry_start + 4 + next_entry.start()) if next_entry else len(after)
    text = after[entry_start:entry_end].strip()
    return text[:max_chars]


def load_profile_data(vault_path, name):
    """Load a profile's frontmatter + latest journal entry."""
    path = vault_path / "30-people" / f"{name}.md"
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    return {
        "frontmatter": parse_frontmatter(text),
        "latest_journal": latest_journal_entry(text),
    }


def days_since(iso_date_string):
    """Return days between today and iso_date_string."""
    if not iso_date_string:
        return None
    try:
        d = datetime.fromisoformat(iso_date_string.split("T")[0]).date()
        return (date.today() - d).days
    except (ValueError, TypeError):
        return None


def build_pulse_input(manifest, vault_path):
    """Assemble structured input for the digest synthesis call."""
    relationships = []
    for rel in manifest.get("relationships", []):
        profile = load_profile_data(vault_path, rel["name"])
        entry = {
            "name": rel["name"],
            "relationship_type": rel.get("relationship_type", "peer"),
            "last_synthesized": rel.get("last_synthesized"),
            "days_since_synth": days_since(rel.get("last_synthesized")),
            "fathom_new_meetings": rel.get("fathom", {}).get("count", 0),
            "has_obsidian_file": rel.get("has_obsidian_file", False),
        }
        if profile:
            fm = profile["frontmatter"]
            entry["health"] = fm.get("health")
            entry["health_score"] = fm.get("health_score")
            entry["health_last_assessed"] = fm.get("health_last_assessed")
            entry["latest_journal"] = profile["latest_journal"]
        relationships.append(entry)

    return {
        "operating_user": manifest.get("operating_user", {}),
        "manifest_date": manifest.get("generated_at"),
        "relationships": relationships,
    }


def build_user_prompt(pulse_input, template):
    """Build the synthesis user prompt."""
    lines = [
        f"Operating user: {pulse_input['operating_user'].get('name')} ({pulse_input['operating_user'].get('email')})",
        f"Manifest date: {pulse_input['manifest_date']}",
        f"Relationships tracked: {len(pulse_input['relationships'])}",
        "",
        "## Per-relationship data",
        "",
    ]
    for r in pulse_input["relationships"]:
        lines.append(f"### {r['name']} ({r['relationship_type']})")
        lines.append(f"  - Health: {r.get('health', '?')} {r.get('health_score', '')}")
        lines.append(f"  - Last assessed: {r.get('health_last_assessed', 'never')}")
        lines.append(f"  - Last synthesized: {r.get('last_synthesized') or 'never'} ({r['days_since_synth']} days ago)" if r['days_since_synth'] is not None else f"  - Last synthesized: never")
        lines.append(f"  - New Fathom meetings: {r['fathom_new_meetings']}")
        lines.append(f"  - Has Obsidian profile: {r['has_obsidian_file']}")
        if r.get("latest_journal"):
            lines.append(f"  - Latest journal entry:")
            for jl in r["latest_journal"].split("\n")[:8]:
                lines.append(f"    > {jl}")
        lines.append("")

    lines.append("\n## Template to follow\n")
    lines.append(template)
    lines.append(
        "\n---\n\nProduce the digest now. Use the operating user's name "
        "when addressing them ('you'). Omit empty sections. Output ONLY the "
        "markdown body — no frontmatter (the caller adds that)."
    )
    return "\n".join(lines)


def find_latest_manifest(cache_dir):
    """Find the most recent biweekly-sweep manifest."""
    manifests = sorted(cache_dir.glob("biweekly-sweep-*.manifest.json"))
    return manifests[-1] if manifests else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Path to manifest JSON (default: latest)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt, do not call API")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault:
        print("ERROR: OBSIDIAN_VAULT_PATH not set", file=sys.stderr)
        sys.exit(1)
    vault_path = Path(vault).expanduser()

    manifest_path = args.manifest
    if manifest_path is None:
        manifest_path = find_latest_manifest(args.cache_dir)
    if manifest_path is None or not manifest_path.exists():
        print(f"ERROR: no manifest found. Run biweekly_sweep.py first.", file=sys.stderr)
        sys.exit(2)

    print(f"Using manifest: {manifest_path}", file=sys.stderr)
    manifest = json.loads(manifest_path.read_text())

    pulse_input = build_pulse_input(manifest, vault_path)

    template_path = SCRIPT_DIR.parent / "references" / "team-pulse-template.md"
    template = template_path.read_text() if template_path.exists() else ""

    user_prompt = build_user_prompt(pulse_input, template)
    print(f"Prompt length: {len(user_prompt)} chars", file=sys.stderr)

    if args.dry_run:
        print("--- DRY RUN ---")
        print(user_prompt)
        return

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
    print("Calling Claude API...", file=sys.stderr)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    body = message.content[0].text
    print(f"Body: {len(body)} chars", file=sys.stderr)

    # Build final markdown with frontmatter
    today = date.today().isoformat()
    user_email = pulse_input["operating_user"].get("email", "")
    rel_count = len(pulse_input["relationships"])

    final = "\n".join([
        "---",
        "type: team-pulse",
        f"date: {today}",
        f"operating_user: {user_email}",
        f"relationships_tracked: {rel_count}",
        "---",
        "",
        body.strip(),
        "",
    ])

    # Write to vault under 30-people/_pulse/
    pulse_dir = vault_path / "30-people" / "_pulse"
    pulse_dir.mkdir(parents=True, exist_ok=True)
    output_path = pulse_dir / f"{today}-team-pulse.md"
    output_path.write_text(final, encoding="utf-8")
    print(f"Pulse written to {output_path}", file=sys.stderr)
    print(str(output_path))


if __name__ == "__main__":
    main()
