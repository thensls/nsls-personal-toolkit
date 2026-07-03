"""Load the personal-toolkit .env into os.environ — idempotent, non-overriding.

Person-intelligence scripts import this for its side effect so that the
*scheduled* biweekly sweep works. A cron / remote-agent run has no interactive
shell to export PEOPLE_OPS_BASE_ID, SLT_BASE_ID, LOP_BASE_ID, OBSIDIAN_VAULT_PATH,
etc., so without this the Airtable fetches silently return nothing and every
profile is built Fathom-only.

Rules:
  * Already-set vars always win — we never overwrite os.environ. So an explicit
    `export FOO=...` or `FOO=... python3.12 script.py` still takes precedence.
  * First existing .env in the candidate list wins; we don't merge across files.

The real .env lives at ~/.claude/local-plugins/nsls-personal-toolkit/.env and is
git-ignored, so it is NOT inside the repo clone that __file__ resolves into —
hence the explicit canonical path before the walk-up fallback.
"""
import os
from pathlib import Path

_CANONICAL = Path.home() / ".claude/local-plugins/nsls-personal-toolkit/.env"


def _candidate_env_files():
    override = os.environ.get("PERSONAL_TOOLKIT_ENV")
    if override:
        yield Path(override).expanduser()
    yield _CANONICAL
    # Walk up from this file (covers a checkout where .env sits at the repo root).
    here = Path(__file__).resolve()
    for parent in here.parents:
        yield parent / ".env"
        if parent.name == "nsls-personal-toolkit":
            break


def _apply(env_file):
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def load_env():
    """Load the first existing candidate .env. Returns the path used, or None."""
    for env_file in _candidate_env_files():
        try:
            if env_file.is_file():
                _apply(env_file)
                return env_file
        except OSError:
            continue
    return None


# Load on import — scripts only need `import load_dotenv_local`.
load_env()
