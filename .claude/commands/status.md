# Git Status Overview

Show a quick overview of the current repository state.

## Instructions

Run these commands and present a clear summary to the user:

1. `git branch --show-current` - Current branch
2. `git status --short` - Changed files (staged and unstaged)
3. `git log --oneline -5` - Last 5 commits
4. `git rev-list --count origin/main..HEAD` - Commits ahead of main (if not on main)
5. `git rev-list --count HEAD..origin/main` - Commits behind main (if not on main)

Present the information in a clean, readable format.
