#!/usr/bin/env bash
# setup.sh — One-shot setup for a new SLT harvest writer. Idempotent; safe to re-run.
#
# Does what a machine CAN do automatically:
#   1. Clone thensls/nsls-knowledge into your vault (if missing), else freshen it.
#   2. Set the KB clone's commit identity to your @nsls.org email (so Step 0's kb-repo
#      scope matches the SLT allowlist and your commits are attributed to you).
# Then it tells you the two things only Kevin can do (allowlist add + GitHub collaborator)
# and runs verify-setup.sh for the final verdict.
#
# Usage:  bash references/setup.sh [you@nsls.org]
#   The email arg is optional — auto-detected from your global git email or toolkit .env
#   when either is already an @nsls.org address.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"

ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad(){ printf '  \033[31m✗\033[0m %s\n' "$1"; }
info(){ printf '    %s\n' "$1"; }

echo "harvest-meeting setup"
echo "─────────────────────────────"

# --- Resolve vault path (env wins, else toolkit .env) ---
VAULT="${OBSIDIAN_VAULT_PATH:-}"
for envf in \
  "$HOME/.claude/local-plugins/nsls-personal-toolkit/.env" \
  "$HOME/nsls-skills/nsls-personal-toolkit/.env"; do
  [ -n "$VAULT" ] && break
  [ -f "$envf" ] && VAULT="$(grep -h '^OBSIDIAN_VAULT_PATH=' "$envf" | head -1 | cut -d= -f2- | tr -d '"')"
done
if [ -z "$VAULT" ]; then
  bad "OBSIDIAN_VAULT_PATH not set and not found in toolkit .env — run /personal-setup first."
  exit 1
fi
KBDIR="$VAULT/60-nsls-knowledge"

# --- Resolve @nsls.org email: arg > global (if @nsls.org) > toolkit .env (if @nsls.org) ---
EMAIL="${1:-}"
is_nsls(){ case "$1" in *@nsls.org) return 0;; *) return 1;; esac; }
if [ -z "$EMAIL" ]; then
  g="$(git config --global user.email 2>/dev/null)"
  is_nsls "$g" && EMAIL="$g"
fi
if [ -z "$EMAIL" ]; then
  for envf in \
    "$HOME/.claude/local-plugins/nsls-personal-toolkit/.env" \
    "$HOME/nsls-skills/nsls-personal-toolkit/.env"; do
    [ -f "$envf" ] || continue
    e="$(grep -hE '^(BUILDER_EMAIL|OPERATING_USER_EMAIL)=' "$envf" | head -1 | cut -d= -f2- | tr -d '"')"
    is_nsls "$e" && EMAIL="$e" && break
  done
fi

# --- 1. Clone or freshen the KB repo ---
if [ -d "$KBDIR/.git" ]; then
  ok "KB clone present: $KBDIR"
  REMOTE="$(git -C "$KBDIR" remote get-url origin 2>/dev/null)"
  case "$REMOTE" in
    *thensls/nsls-knowledge*) ok "remote OK: $REMOTE" ;;
    *) bad "remote is not thensls/nsls-knowledge: ${REMOTE:-<none>} — fix manually before continuing" ;;
  esac
  if git -C "$KBDIR" pull --ff-only --quiet 2>/dev/null; then ok "clone up to date"; else
    info "couldn't fast-forward (uncommitted/divergent tree or offline) — harvest Step 8 will retry"; fi
else
  info "cloning thensls/nsls-knowledge → $KBDIR ..."
  if git clone --quiet https://github.com/thensls/nsls-knowledge.git "$KBDIR" 2>/tmp/kbclone.err; then
    ok "cloned KB repo"
  else
    bad "clone FAILED:"
    sed 's/^/      /' /tmp/kbclone.err
    info "A 'Repository not found' / 403 means you're not a collaborator yet."
    info "Ask Kevin to add your GitHub account to thensls/nsls-knowledge, then re-run this."
    exit 1
  fi
fi

# --- 2. Set the clone's commit identity ---
if [ -n "$EMAIL" ]; then
  CUR="$(git -C "$KBDIR" config user.email 2>/dev/null)"
  if [ "$CUR" = "$EMAIL" ]; then ok "commit identity already set: $EMAIL"
  else git -C "$KBDIR" config user.email "$EMAIL" && ok "set commit identity: $EMAIL"; fi
else
  bad "couldn't auto-detect your @nsls.org email — set it yourself:"
  info "git -C \"\$OBSIDIAN_VAULT_PATH/60-nsls-knowledge\" config user.email you@nsls.org"
  info "or re-run: bash references/setup.sh you@nsls.org"
fi

# --- 3. Allowlist membership (the part only Kevin can grant) ---
if [ -n "$EMAIL" ]; then
  if git -C "$KBDIR" fetch -q origin main 2>/dev/null \
     && git -C "$KBDIR" show origin/main:_data/kb_authors.txt 2>/dev/null | grep -qxF "$EMAIL"; then
    ok "on the SLT allowlist ($EMAIL)"
  else
    bad "$EMAIL is NOT on the SLT allowlist yet."
    info "Ask Kevin to add it to _data/kb_authors.txt in thensls/nsls-knowledge (one commit)."
    info "Until then your harvests route to your private LOCAL KB."
  fi
fi

# --- 4. Final verdict ---
echo "─────────────────────────────"
echo "running verification..."
echo
bash "$HERE/verify-setup.sh"
