# Stash Changes

Stash or restore work in progress.

## Instructions

Check the argument provided: $ARGUMENTS

If argument is "pop", "apply", or "restore":
1. Run `git stash list` to show available stashes
2. Run `git stash pop` to restore the most recent stash

If argument is "list":
1. Run `git stash list` to show all stashes

If no argument or argument is "save" or "push":
1. Run `git status` to check for changes
2. If no changes, inform user there's nothing to stash
3. Otherwise run `git stash push -m "WIP: <brief description of changes>"`
4. Confirm the stash was created
