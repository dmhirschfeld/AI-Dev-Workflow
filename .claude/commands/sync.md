# Sync with Remote

Pull the latest changes from the remote repository.

## Instructions

1. Run `git status` to check for uncommitted changes
2. If there are uncommitted changes, warn the user and ask if they want to stash them first
3. Run `git fetch origin` to get latest remote state
4. Run `git pull` to pull changes
5. If there were stashed changes, ask if user wants to restore them
6. Report the sync result to the user (how many commits pulled, any conflicts)
