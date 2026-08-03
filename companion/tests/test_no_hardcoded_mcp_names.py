"""Guard against hardcoded MCP connector tool names in skill docs (T-10).

claude.ai connector tools are namespaced ``mcp__<uuid>__<tool>``, where the
UUID is minted per account/installation — a hardcoded name can never resolve
on another builder's machine, so the model silently skips the call and the
feature no-ops. This killed the day-planner's entire task-sync half for
months: every Asana read and write pointed at ``mcp__claude_ai_Asana__*``, a
namespace that has never existed anywhere.

Rule: skill docs reference connector capabilities by intent ("the Asana
connector's get_my_tasks — resolve the live name from this session's tools").
The only ``mcp__`` tokens allowed in skill prose are:
  - ``mcp__<uuid>__``        the literal placeholder used to EXPLAIN the rule
  - ``mcp__apple-health__*`` a local MCP server with a stable install-time name
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# mcp__ followed by a real identifier character — the explanatory placeholder
# mcp__<uuid>__ starts with '<' and is deliberately not matched.
HARDCODED = re.compile(r"mcp__(?!<)[A-Za-z0-9]")
ALLOWED = re.compile(r"mcp__apple-health__")


def test_no_hardcoded_connector_tool_names():
    offenders = []
    for md in sorted(REPO_ROOT.glob("skills/**/*.md")):
        text = md.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in HARDCODED.finditer(line):
                if ALLOWED.match(line, m.start()):
                    continue
                offenders.append(
                    f"{md.relative_to(REPO_ROOT)}:{lineno}: {line.strip()[:110]}"
                )
                break  # one report per line is enough
    assert not offenders, (
        "Hardcoded MCP tool names found. Connector tools are UUID-namespaced "
        "per machine and can never resolve on another install — reference the "
        "capability by intent and resolve the live name at runtime:\n"
        + "\n".join(offenders)
    )
