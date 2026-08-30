#!/usr/bin/env bash
# verify-setup.sh — Check that /harvest-meeting will write to the COMPANY KB, not silently
# fall back to a private local KB. Safe to run anytime: reads only, writes nothing, no harvest.
#
# WHAT THIS CHECKS (and, just as important, what it does NOT):
#   harvest-meeting writes via `git clone` + `commit` + `git push` to thensls/nsls-knowledge.
#   It does NOT use the kb-gateway (that service only powers the bot + kb.nsls.org read path).
#   So there is no KB_GATEWAY_URL / token to verify here — the ONLY thing that decides success
#   is: does one of your git-identity scopes match the SLT allowlist?
#
# The allowlist lives in the KB repo (_data/kb_authors.txt) and is read LIVE from origin/main,
# exactly like Step 0 in SKILL.md. The copy shipped with the toolkit is an offline fallback.
# If you change the scope list or allowlist source in Step 0, update this script too.
#
# Usage:  bash references/verify-setup.sh
set -u
TMP_AL="$(mktemp)"; trap 'rm -f "$TMP_AL"' EXIT

ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
info(){ printf '    %s\n' "$1"; }

# --- Resolve vault path (env wins, else toolkit .env) ---
VAULT="${OBSIDIAN_VAULT_PATH:-}"
for envf in \
  "$HOME/.claude/local-plugins/nsls-personal-toolkit/.env" \
  "$HOME/nsls-skills/nsls-personal-toolkit/.env"; do
  [ -n "$VAULT" ] && break
  [ -f "$envf" ] && VAULT="$(grep -h '^OBSIDIAN_VAULT_PATH=' "$envf" | head -1 | cut -d= -f2- | tr -d '"')"
done
KBDIR="$VAULT/60-nsls-knowledge"

echo "harvest-meeting setup check"
echo "─────────────────────────────"

# --- Load the allowlist: LIVE from the KB repo (source of truth), shipped copy as fallback ---
AL=""; AL_SRC=""
if [ -d "$KBDIR/.git" ] && git -C "$KBDIR" fetch -q origin main 2>/dev/null \
   && git -C "$KBDIR" show origin/main:_data/kb_authors.txt >"$TMP_AL" 2>/dev/null; then
  AL="$TMP_AL"; AL_SRC="KB repo origin/main:_data/kb_authors.txt (live)"
else
  for p in \
    "$HOME/.claude/local-plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt" \
    "$HOME/nsls-skills/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt" \
    "$HOME/.claude/plugins/nsls-personal-toolkit/skills/harvest-meeting/kb_authors.txt"; do
    [ -f "$p" ] && AL="$p" && AL_SRC="toolkit shipped copy — fallback (couldn't reach KB repo): $p" && break
  done
fi
[ -n "$AL" ] && ok "allowlist: $AL_SRC" || { bad "kb_authors.txt not found (no KB clone, no shipped copy) — is the toolkit installed?"; exit 1; }

# --- Gather candidate identities from every stable scope (same set as Step 0) ---
ENVEMAIL=""
for envf in \
  "$HOME/.claude/local-plugins/nsls-personal-toolkit/.env" \
  "$HOME/nsls-skills/nsls-personal-toolkit/.env"; do
  [ -n "$ENVEMAIL" ] && break
  [ -f "$envf" ] && ENVEMAIL="$(grep -hE '^(BUILDER_EMAIL|OPERATING_USER_EMAIL)=' "$envf" | head -1 | cut -d= -f2- | tr -d '"')"
done

MATCH=""
echo "identity scopes (any one on the allowlist → COMPANY KB):"
check_scope(){ # $1=label $2=email
  local label="$1" email="$2"
  if [ -z "$email" ]; then info "$label: (unset)"; return; fi
  if grep -qxF "$email" "$AL"; then ok "$label: $email — on allowlist"; MATCH=1
  else info "$label: $email — not on allowlist"; fi
}
check_scope "kb-repo (authors commits)" "$(git -C "$KBDIR" config user.email 2>/dev/null)"
check_scope "global"                    "$(git config --global user.email 2>/dev/null)"
check_scope "\$GIT_AUTHOR_EMAIL"        "${GIT_AUTHOR_EMAIL:-}"
check_scope "toolkit .env"              "$ENVEMAIL"

# --- Clone + write access ---
echo "clone + write access:"
if [ -d "$KBDIR/.git" ]; then
  ok "clone present: $KBDIR"
  REMOTE="$(git -C "$KBDIR" remote get-url origin 2>/dev/null)"
  case "$REMOTE" in
    *thensls/nsls-knowledge*) ok "remote: $REMOTE" ;;
    "") bad "no 'origin' remote configured" ;;
    *) bad "remote is not thensls/nsls-knowledge: $REMOTE" ;;
  esac
  if git -C "$KBDIR" ls-remote origin -h refs/heads/main >/dev/null 2>&1; then
    ok "push access: GitHub reachable + authorized"
  else
    bad "push access FAILED — you likely need collaborator access on thensls/nsls-knowledge (ask Marcus) or GitHub auth (gh auth login)"
  fi
else
  bad "clone MISSING at $KBDIR"
  info "fix: git clone https://github.com/thensls/nsls-knowledge.git \"\$OBSIDIAN_VAULT_PATH/60-nsls-knowledge\""
fi

# --- Verdict ---
echo "─────────────────────────────"
if [ -n "$MATCH" ]; then
  printf '  ROUTE: \033[32mCOMPANY KB ✓\033[0m  — harvest will commit + push to thensls/nsls-knowledge\n'
else
  printf '  ROUTE: \033[33mLOCAL KB ⚠\033[0m  — harvest will NOT reach the shared KB\n'
  echo "  To route to the company KB, either:"
  echo "    • ask Marcus to add your @nsls.org email to _data/kb_authors.txt in the KB repo"
  echo "      (one commit — picked up automatically on your next harvest), OR"
  echo "    • fix a wrong/typo'd git email so a scope above matches, e.g.:"
  echo "        git -C \"\$OBSIDIAN_VAULT_PATH/60-nsls-knowledge\" config user.email you@nsls.org"
fi
