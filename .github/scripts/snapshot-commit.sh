#!/usr/bin/env bash
# Commit and push whatever the snapshot collector just wrote.
#
# Called twice per pass -- once for the pool rows, once for the sellability rows -- so the
# irreplaceable half is safely pushed before the optional half is even attempted.
#
# THE PUSH RETRIES, AND THAT IS THE POINT. The previous version was a bare `git push`
# after a depth-1 checkout taken at job start. The measured checkout-to-push window over
# eleven steady-state passes was 142-265 seconds; any push landing inside it -- a human
# commit, or the other snapshot step -- makes this one non-fast-forward, the step exits
# non-zero, the runner is destroyed, and that pass's rows are gone. There is no second
# copy: upstream serves current state only, so a day not recorded never existed.
#
# Worse than the loss is that the loss is invisible. A pass that was attempted and lost
# reads downstream exactly like a pass in which no pools launched. That is the same
# gap-versus-finding collapse this project keeps re-committing, written this time into
# the archive itself, where no later analysis can undo it.
#
# Rebase is safe here: the bot only ever APPENDS to files under bench/snapshots/, which no
# human edits, so there is no semantic conflict to resolve.
#
# WHY IT REFUSES OFF GITHUB ACTIONS. It has no local mode: with any argument or none, its first
# act is to write the snapshot bot's identity into this clone's git config, which every worktree
# of the clone shares; then it commits whatever is under bench/snapshots/ and pushes. On a
# laptop that is always an accident -- run by hand to see what it does, or from a task
# worktree -- so it runs only where GitHub Actions sets GITHUB_ACTIONS=true, and anywhere else
# it stops with exit 2 before the first git command. tests/test_bot_commits_stay_green.py runs
# both sides for real, in scratch repositories: the refusal, and on Actions nothing new, a
# commit and a push, and a rejected push that is rebased and retried.
set -uo pipefail

# Everything below commits and pushes, so none of it runs off GitHub Actions (see the header).
if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
  echo "snapshot-commit.sh: refusing to run: it writes the snapshot bot's identity into this" >&2
  echo "  clone's git config, commits what is under bench/snapshots/ and pushes; it runs only on" >&2
  echo "  GitHub Actions, where GITHUB_ACTIONS is 'true'." >&2
  echo "  Do not set GITHUB_ACTIONS by hand to get past this: that commits and pushes from this clone as the bot." >&2
  exit 2
fi

what="${1:-snapshot}"

git config user.name "vetagent-snapshot[bot]"
git config user.email "noreply@vetagent.dev"
git add bench/snapshots/

if git diff --staged --quiet; then
  # Zero rows means every upstream is down. That deserves a warning, not silence.
  echo "::warning::no ${what} rows collected -- every upstream may be down"
  exit 0
fi

days=$(ls bench/snapshots/pools-*.ndjson 2>/dev/null | wc -l)
rows=$(cat bench/snapshots/pools-*.ndjson 2>/dev/null | wc -l)
git commit -m "Snapshot $(date -u +%F) (${what}): ${days} days, ${rows} rows total"

for attempt in 1 2 3 4 5; do
  if git push; then
    echo "pushed on attempt ${attempt}"
    exit 0
  fi
  echo "::notice::push rejected (attempt ${attempt}); rebasing onto origin and retrying"
  git pull --rebase --autostash origin "${GITHUB_REF_NAME}" || true
  sleep $(( attempt * 10 ))
done

echo "::error::could not push ${what} rows after 5 attempts -- THIS PASS IS LOST"
exit 1
