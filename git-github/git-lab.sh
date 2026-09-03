#!/usr/bin/env bash
#
# Git homework, both tasks, in a throwaway repository so the practice history
# never lands in the homework repo.

set -uo pipefail

LAB="${1:-/tmp/git-lab-$$}"
rm -rf "$LAB"
mkdir -p "$LAB"
cd "$LAB"

step() { printf '\n$ %s\n' "$*"; "$@" 2>&1; }

echo "=============================================================="
echo "TASK 1 - git commit -m  vs  git commit -a -m"
echo "=============================================================="

step git init -b main -q .
git config user.name  "Vibhuti Bhatnagar"
git config user.email "vibhuti.bhatnagar@scalerailabs.com"

printf 'line one\n' > tracked.txt
step git add tracked.txt
step git commit -q -m "Add tracked.txt"

echo
echo "Now make two changes at once:"
echo "  - modify tracked.txt   (a TRACKED file)"
echo "  - create untracked.txt (an UNTRACKED file)"
printf 'line two\n' >> tracked.txt
printf 'brand new file\n'  > untracked.txt

step git status --short
echo "  M = modified and tracked, ?? = untracked"

echo
echo "-------- git commit -m  (nothing staged) --------"
printf '\n$ git commit -m "try to commit without staging"\n'
git commit -m "try to commit without staging" 2>&1 | head -8
echo
echo "Refused. Plain -m commits only what is already in the staging area,"
echo "and nothing was added, so there was nothing to commit."

echo
echo "-------- git commit -a -m --------"
step git commit -a -q -m "Commit with -a"
step git show --stat --oneline HEAD

echo
echo "\$ git status --short"
git status --short
echo "  untracked.txt is STILL untracked."
echo
echo "RESULT:"
echo "  modified tracked file  -> included by git commit -a"
echo "  new untracked file     -> NOT included by git commit -a"
echo
echo "-a stages tracked files that were modified or deleted, then commits."
echo "It never adds a file git has not seen before. Those still need git add."

step git add untracked.txt
step git commit -q -m "Add untracked.txt explicitly"

echo
echo
echo "=============================================================="
echo "TASK 2 - cherry-pick"
echo "=============================================================="

rm -rf "$LAB/cherry"
mkdir -p "$LAB/cherry"
cd "$LAB/cherry"
git init -b main -q .
git config user.name  "Vibhuti Bhatnagar"
git config user.email "vibhuti.bhatnagar@scalerailabs.com"

echo
echo "--- Three commits on main ---"
printf 'base notes\n' > notes.txt
git add notes.txt && git commit -q -m "Add base notes"
printf 'linux note\n' >> notes.txt
git commit -aq -m "Add Linux note"
printf 'docker note\n' >> notes.txt
git commit -aq -m "Add Docker note"

step git log --oneline

echo
echo "--- A new branch with three more commits ---"
step git switch -c command-notes
printf 'networking note\n' >> notes.txt
git commit -aq -m "Add networking note"
printf 'journalctl note\n' >> notes.txt
git commit -aq -m "Add journalctl note"
printf 'cherry-pick note\n' >> notes.txt
git commit -aq -m "Add cherry-pick note"

step git log --oneline

echo
echo "--- Both branches ---"
step git log --oneline --all --decorate --graph

echo
echo "--- Identify the one commit to take ---"
TARGET=$(git log --format='%H %s' | awk '/Add networking note/ {print $1}')
printf '\n$ git log --format="%%h %%s" | grep "Add networking note"\n'
git log --format='%h %s' | grep 'Add networking note'
echo
echo "Target commit: $TARGET"

echo
echo "--- Back to main, which does NOT have it ---"
step git switch main

echo
echo "main also moves on in the meantime, so the two branches genuinely diverge."
echo "Without this the cherry-pick would land straight onto the commit's own"
echo "parent and git would rebuild a byte-identical commit - same tree, same"
echo "parent, same timestamp, same SHA - which hides what cherry-pick does."
echo "main's own commit touches a DIFFERENT file, so the pick applies cleanly."
echo "A conflicting pick is demonstrated separately at the end."
printf '# Command notes lab\n' > README.md
git add README.md
git commit -q -m "Add README on main"

step git log --oneline
printf '\n$ cat notes.txt\n'
cat notes.txt
printf '\n$ grep -c networking notes.txt   # 0 = not present on main\n'
grep -c networking notes.txt

echo
echo "--- Cherry-pick just that one commit ---"
step git cherry-pick "$TARGET"

echo
echo "--- Verify ---"
step git log --oneline
printf '\n$ cat notes.txt\n'
cat notes.txt
printf '\n$ grep networking notes.txt\n'
grep networking notes.txt

NEW=$(git rev-parse HEAD)
echo
echo "=============================================================="
echo "The new commit is a COPY, not the same commit"
echo "=============================================================="
printf 'original commit on command-notes : %s\n' "$TARGET"
printf 'new commit on main               : %s\n' "$NEW"
if [ "$TARGET" = "$NEW" ]; then
    echo
    echo "Identical - which only happens when the pick lands on the commit's own parent."
else
    echo
    echo "Different SHAs. A commit's hash covers its parent and its committer"
    echo "timestamp, and here the parent changed, so the copy hashes differently."
fi
echo "The patch itself is unchanged:"
printf '\n$ diff <(git show --format="" %s) <(git show --format="" %s) && echo "the two patches are identical"\n' \
    "${TARGET:0:7}" "${NEW:0:7}"
diff <(git show --format='' "$TARGET") <(git show --format='' "$NEW") \
    && echo "the two patches are identical"

echo
echo "\$ git log --oneline --all --decorate --graph"
git log --oneline --all --decorate --graph

echo
echo "Note that 'Add journalctl note' and 'Add cherry-pick note' were left"
echo "behind on the branch. That is the point of cherry-pick: take one commit,"
echo "not everything up to it, which is what a merge or rebase would do."


echo
echo
echo "=============================================================="
echo "APPENDIX - what a conflicting cherry-pick looks like"
echo "=============================================================="
echo "First let main append its own line to the same end-of-file region:"
printf 'compose note\n' >> notes.txt
git commit -aq -m "Add Compose note on main"
printf '\n$ cat notes.txt\n'
cat notes.txt
echo
echo "The branch's next commit expects 'networking note' to be the last line,"
echo "but on main it is now followed by 'compose note'. Picking it must conflict."

SECOND=$(git log command-notes --format='%H %s' | awk '/Add journalctl note/ {print $1}')
printf '\n$ git cherry-pick %s   # "Add journalctl note"\n' "${SECOND:0:7}"
git cherry-pick "$SECOND" 2>&1 | head -6

printf '\n$ git status --short\n'
git status --short
echo "  UU = both sides modified the same region"

printf '\n$ cat notes.txt\n'
cat notes.txt

echo
echo "Resolve by keeping both sides, then continue:"
printf 'base notes\nlinux note\ndocker note\nnetworking note\ncompose note\njournalctl note\n' > notes.txt
step git add notes.txt
printf '\n$ git cherry-pick --continue --no-edit\n'
git cherry-pick --continue --no-edit 2>&1 | head -4

printf '\n$ git log --oneline\n'
git log --oneline
printf '\n$ cat notes.txt\n'
cat notes.txt
echo
echo "git cherry-pick --abort would have thrown the whole thing away instead."

echo
echo "Lab directory: $LAB"
