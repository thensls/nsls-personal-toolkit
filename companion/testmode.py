"""Test-mode vault resolution + safety guards.

The `-t` flag on open-day / close-day / reset-day points the whole system at a
throwaway *test vault* instead of the user's real Obsidian vault, so trying the
companion never touches real daily notes. Per the design, nothing forks on a
code path: `-t` simply redirects ``OBSIDIAN_VAULT_PATH`` to the test vault, and
everything downstream (server, skills, reset) operates on it normally.

Everything keys off ONE directory name — ``companion-test-vault``:

* the server flips its TEST marker when the vault it's serving has that name
  (:func:`is_test_vault`), and
* reset-day asserts that name before it deletes anything in test mode
  (:func:`assert_test_vault`),

so the visible warning and the delete guard can never disagree.
"""

from pathlib import Path

# The single source of truth. The server's TEST marker and reset-day's delete
# guard both compare against this exact directory name.
TEST_VAULT_NAME = "companion-test-vault"

# Toolkit root = the parent of the ``companion`` package dir (the same anchor
# cli.py uses for TEMPLATES_DIR). Installed, that's
# ~/.claude/local-plugins/nsls-personal-toolkit/ ; in a worktree it's the
# worktree root. The test vault sits alongside the package either way.
_TOOLKIT_ROOT = Path(__file__).resolve().parent.parent


def default_test_vault() -> Path:
    """Canonical location of the throwaway test vault."""
    return _TOOLKIT_ROOT / TEST_VAULT_NAME


def is_test_vault(path) -> bool:
    """True iff ``path`` resolves to a directory named ``companion-test-vault``.

    Lenient by design (any such directory counts) because it only drives the
    cosmetic TEST marker. The destructive guard is :func:`assert_test_vault`.
    """
    if not path:
        return False
    return Path(path).resolve().name == TEST_VAULT_NAME


def assert_test_vault(path) -> Path:
    """Return the resolved path, or raise ``ValueError`` if it isn't a test vault.

    reset-day ``-t`` calls this *before* deleting, so a misconfigured
    ``OBSIDIAN_VAULT_PATH`` (e.g. still pointing at the real vault) can never
    wipe real data under the guise of test mode.
    """
    if not path:
        raise ValueError("No vault path given; refusing to run a test-mode reset.")
    resolved = Path(path).resolve()
    if resolved.name != TEST_VAULT_NAME:
        raise ValueError(
            f"Refusing test-mode operation on a non-test vault: {resolved}\n"
            f"The test vault directory must be named {TEST_VAULT_NAME!r}."
        )
    return resolved


_SAMPLE_HABITS = """# Daily Habits

## Active

- id: walk
  name: Walk
  emoji: 🚶
  target: 30min
  frequency: daily

- id: read
  name: Read 15m
  emoji: 📖
  target: 15min
  frequency: daily

- id: meditate
  name: Meditate
  emoji: 🧘
  target: 10min
  frequency: daily
"""


def _sample_day_note() -> str:
    """A clearly-sample day in the *planning* state, so `open day -t` lands on
    the morning planning screen (pick your Top 3) — the most important first
    screen — with a few suggestions to choose from, rather than jumping past it
    into the Command Center."""
    return """---
status: planning
---
# Daily Note — (sample test day)

## Morning Check-in

### AI Suggested: Tomorrow's Top 3
1. Review the Q3 LOP draft
2. Reply to the vendor contract thread
3. Prep the board update

### My Top 3
1. [ ]
2. [ ]
3. [ ]

### Bonus

### Habits
- [ ] **Walk**
- [ ] **Read 15m**
- [ ] **Meditate**
"""


# Made-up Jira issues: project DEMO, every summary marked [TEST], due dates as
# days from today so the file never goes stale. One done yesterday (should
# count as done, not suggested) and one in an excluded support project (HELP,
# should never appear).
_JIRA_FIXTURE = """{
  "note": "Fake Jira issues for open-day test mode only. Never real data.",
  "issues": [
    {"key": "DEMO-101", "summary": "[TEST] Fix the enrollment report totals", "status": "In Progress", "statusCategory": "In Progress", "priority": "High", "due_in_days": -2, "updated_days_ago": 1, "project": "DEMO"},
    {"key": "DEMO-102", "summary": "[TEST] Ship the chapter dashboard filter", "status": "To Do", "statusCategory": "To Do", "priority": "High", "due_in_days": 0, "updated_days_ago": 3, "project": "DEMO"},
    {"key": "DEMO-103", "summary": "[TEST] Review the data dictionary draft", "status": "In Review", "statusCategory": "In Progress", "priority": "Medium", "due_in_days": 1, "updated_days_ago": 0, "project": "DEMO"},
    {"key": "DEMO-104", "summary": "[TEST] Add the spring cohort to the weekly export", "status": "To Do", "statusCategory": "To Do", "priority": "Medium", "due_in_days": 4, "updated_days_ago": 6, "project": "DEMO"},
    {"key": "DEMO-105", "summary": "[TEST] Blocked: waiting on the warehouse access request", "status": "Blocked", "statusCategory": "In Progress", "priority": "Medium", "due_in_days": null, "updated_days_ago": 9, "project": "DEMO"},
    {"key": "DEMO-106", "summary": "[TEST] Clean up old Snowflake views", "status": "To Do", "statusCategory": "To Do", "priority": "Low", "due_in_days": null, "updated_days_ago": 30, "project": "DEMO"},
    {"key": "DEMO-107", "summary": "[TEST] Document the invitations pipeline", "status": "To Do", "statusCategory": "To Do", "priority": "Low", "due_in_days": 10, "updated_days_ago": 2, "project": "DEMO"},
    {"key": "DEMO-108", "summary": "[TEST] Answer the school's data request", "status": "Done", "statusCategory": "Done", "priority": "High", "due_in_days": -1, "updated_days_ago": 1, "resolved_days_ago": 1, "project": "DEMO"},
    {"key": "HELP-0000", "summary": "[TEST] Support ticket that must never be shown", "status": "Open", "statusCategory": "To Do", "priority": "High", "due_in_days": 0, "updated_days_ago": 0, "project": "HELP"}
  ]
}
"""


def ensure_test_vault(seed_today: bool = True) -> Path:
    """Create + seed the test vault and return its path. Idempotent.

    Creates the standard subdirs and habits files via the same
    ``ensure_vault_structure`` the real vault uses, and — only when today's note
    is absent — drops in a clearly-labelled sample day so the companion has
    something to show on the very first ``-t`` run. Never overwrites an existing
    note.
    """
    # Imported lazily to avoid a circular import (cli imports this module).
    from companion.cli import ensure_vault_structure
    from datetime import date

    vault = default_test_vault()
    vault.mkdir(parents=True, exist_ok=True)
    ensure_vault_structure(vault)

    # ensure_vault_structure seeds habits.md from a template, but the template
    # is intentionally empty (just an onboarding placeholder). A *practice*
    # vault is more useful with a few habits to tick, so seed the sample
    # whenever no actual habit (`- id:`) is defined yet — without clobbering
    # habits the user has since added in the test vault.
    habits = vault / "30-habits" / "habits.md"
    has_habit = habits.exists() and "- id:" in habits.read_text(encoding="utf-8")
    if not has_habit:
        habits.parent.mkdir(parents=True, exist_ok=True)
        habits.write_text(_SAMPLE_HABITS, encoding="utf-8", newline="")

    # Fake Jira issues for `open day -t` with `task_board: jira`: open-day
    # reads this file instead of the connector, in the test vault only.
    fixture = vault / "50-reference" / "jira-fixture.json"
    if not fixture.exists():
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(_JIRA_FIXTURE, encoding="utf-8", newline="")

    if seed_today:
        today_note = vault / "01-daily" / f"{date.today().isoformat()}.md"
        if not today_note.exists():
            today_note.parent.mkdir(parents=True, exist_ok=True)
            today_note.write_text(_sample_day_note(), encoding="utf-8", newline="")

    return vault
