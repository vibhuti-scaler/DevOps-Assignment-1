# Git and GitHub

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

Both tasks are in [`git-lab.sh`](git-lab.sh), which builds a throwaway repository so the practice
history never lands in this one. Full transcript: [cherry-pick-output.txt](cherry-pick-output.txt).

```bash
./git-lab.sh
```

## Task 1 — `git commit -m` vs `git commit -a -m`

I set up one of each kind of change and committed once, so the difference is visible in a single
result:

```text
$ git status --short
 M tracked.txt      <- modified, and git already knows this file
?? untracked.txt    <- brand new, git has never seen it
```

**`git commit -m` with nothing staged does nothing at all:**

```text
$ git commit -m "try to commit without staging"
On branch main
Changes not staged for commit:
	modified:   tracked.txt
Untracked files:
```

It commits **only what is already in the staging area**. Nothing was added, so there was nothing to
commit.

**`git commit -a -m` picks up the tracked file — and only that one:**

```text
$ git commit -a -q -m "Commit with -a"
$ git show --stat --oneline HEAD
564bebc Commit with -a
 tracked.txt | 1 +
 1 file changed, 1 insertion(+)

$ git status --short
?? untracked.txt     <- still untracked
```

| Change | `git commit -m` | `git commit -a -m` |
| --- | --- | --- |
| Modified **tracked** file | only if `git add`ed first | staged and committed automatically |
| Deleted **tracked** file | only if staged first | staged and committed automatically |
| New **untracked** file | needs `git add` | **still needs `git add`** |

`-a` is shorthand for "stage every tracked file that changed, then commit". It never adds a file
git has not seen before — that is the trap. You think `-a` means "commit everything", push, and the
new file is missing.

I use `-a` for quick single-purpose edits to files already in the repo, after checking
`git status`. When a change spans several files, an explicit `git add` is clearer and keeps
unrelated edits out of the commit.

## Task 2 — cherry-pick

Three commits on `main`, then a branch with three more:

```text
* 8817e7d (command-notes) Add cherry-pick note
* bf2b248 Add journalctl note
* 5b52e29 Add networking note
* 1e73def (main) Add Docker note
* 943a537 Add Linux note
* bc2ecba Add base notes
```

`main` then gets a commit of its own so the branches genuinely diverge (see the note below on why
that matters). Pick the one commit wanted:

```bash
git switch main
git cherry-pick 5b52e29        # "Add networking note"
```

```text
[main fc71a37] Add networking note
 1 file changed, 1 insertion(+)
```

Verified — the change is on `main`:

```text
$ git log --oneline
fc71a37 Add networking note
6c02a9a Add README on main
1e73def Add Docker note
943a537 Add Linux note
bc2ecba Add base notes

$ cat notes.txt
base notes
linux note
docker note
networking note
```

And the two commits it did **not** take are still only on the branch:

```text
* 8817e7d (command-notes) Add cherry-pick note
* bf2b248 Add journalctl note
* 5b52e29 Add networking note
| * fc71a37 (HEAD -> main) Add networking note
| * 6c02a9a Add README on main
|/
* 1e73def Add Docker note
```

That is the whole point. A merge or rebase would have brought everything up to that commit;
cherry-pick takes exactly one.

## The copy has a different SHA

```text
original on command-notes : 5b52e297a9c6a74f46e9583cce104cbf2b1ecd32
new on main               : fc71a37a206a84ae6ce11c619a983b7af23cf6da
```

A commit hash covers its parent, its tree, and its timestamps. The parent changed, so the hash
changed — even though `diff` confirms the two patches are byte-identical. Cherry-pick **replays a
change as a new commit**; it does not move or share the original.

### Something I got wrong first time

My first version of this lab cherry-picked the commit straight onto `main` without giving `main` a
commit of its own. The result was a **byte-identical SHA** — same tree, same parent, same
timestamp, so git rebuilt exactly the same object. It looked like cherry-pick had somehow moved the
original commit.

It had not: picking a commit onto its own parent just recreates it. The lab now adds a commit to
`main` first, so the branches actually diverge and the copy is visibly a different object.

## Appendix — a conflicting cherry-pick

Cherry-pick applies a **patch**, so it fails when the surrounding lines have moved. After `main`
appended its own line to the same end-of-file region:

```text
$ git cherry-pick bf2b248
Auto-merging notes.txt
CONFLICT (content): Merge conflict in notes.txt
error: could not apply bf2b248... Add journalctl note

$ git status --short
UU notes.txt          <- both sides changed the same region
```

```text
networking note
<<<<<<< HEAD
compose note
=======
journalctl note
>>>>>>> bf2b248 (Add journalctl note)
```

Resolve, stage, continue:

```bash
# edit notes.txt to keep both lines
git add notes.txt
git cherry-pick --continue --no-edit
```

`git cherry-pick --abort` discards it instead and restores the branch to its previous state.
