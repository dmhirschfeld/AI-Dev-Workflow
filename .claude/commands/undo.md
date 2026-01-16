# Undo Last Commit

Undo the last commit while keeping changes staged.

## Instructions

1. Run `git log --oneline -3` to show recent commits
2. Confirm with the user which commit will be undone
3. Check if the commit has been pushed with `git status` (look for "ahead" count)
4. If already pushed, warn the user this will require a force push and ask for confirmation
5. Run `git reset --soft HEAD~1` to undo the commit but keep changes staged
6. Run `git status` to show the result
7. Inform the user their changes are now staged and ready to be re-committed
