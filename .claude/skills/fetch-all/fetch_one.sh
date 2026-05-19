#!/usr/bin/env bash
# fetch-all: fast-forward staging + main in a single repo to origin.
#
# Usage:  fetch_one.sh <repo-dir>
#
# - If a branch is not checked out and origin has it, runs
#   `git fetch origin BR:BR`. Non-fast-forward → fail (we don't force).
# - If a branch IS checked out, runs `git pull --ff-only origin BR`.
# - If origin has no such branch, skips quietly.
#
# Prints a one-line status per branch. Always exits 0 so a foreach loop
# keeps going; the caller scans stdout for [fail].

set -u

repo_dir="${1:-.}"
cd "$repo_dir" || { echo "[fail] cannot cd into $repo_dir"; exit 0; }

repo_name="$(basename "$(pwd)")"
echo "=== $repo_name ==="

current_branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")"

# Single fetch so we have fresh remote refs to compare against.
# Failure here (network, auth) is not fatal — we'll just report per-branch.
git fetch --quiet origin 2>/dev/null || true

for br in staging main; do
  # Does origin have this branch?
  if ! git ls-remote --exit-code --heads origin "$br" >/dev/null 2>&1; then
    printf "  %-8s [skip]  no origin/%s\n" "$br" "$br"
    continue
  fi

  if [ "$br" = "$current_branch" ]; then
    # Currently checked out — fast-forward via pull.
    out="$(git pull --ff-only origin "$br" 2>&1)"
    rc=$?
    if [ $rc -eq 0 ]; then
      if echo "$out" | grep -q "Already up to date"; then
        printf "  %-8s [ok]    already up to date (checked out)\n" "$br"
      else
        # Try to extract the range from "Updating a1b2c3d..d4e5f6a"
        range="$(echo "$out" | grep -oE 'Updating [0-9a-f]+\.\.[0-9a-f]+' | sed 's/Updating //')"
        printf "  %-8s [ok]    fast-forward %s (checked out)\n" "$br" "${range:-pulled}"
      fi
    else
      first_err="$(echo "$out" | grep -E 'fatal|error|not possible' | head -1)"
      printf "  %-8s [fail]  pull --ff-only failed: %s\n" "$br" "${first_err:-see git output}"
    fi
  else
    # Not checked out — update local ref directly.
    out="$(git fetch origin "$br:$br" 2>&1)"
    rc=$?
    if [ $rc -eq 0 ]; then
      # `git fetch X:X` prints e.g. "   a1b2c3d..d4e5f6a  staging    -> staging"
      range="$(echo "$out" | grep -oE '[0-9a-f]+\.\.[0-9a-f]+' | head -1)"
      if [ -n "$range" ]; then
        printf "  %-8s [ok]    fast-forward %s\n" "$br" "$range"
      else
        printf "  %-8s [ok]    already up to date\n" "$br"
      fi
    else
      first_err="$(echo "$out" | grep -E 'rejected|fatal|error' | head -1)"
      printf "  %-8s [fail]  fetch %s:%s rejected: %s\n" "$br" "$br" "$br" "${first_err:-see git output}"
    fi
  fi
done

echo
exit 0
