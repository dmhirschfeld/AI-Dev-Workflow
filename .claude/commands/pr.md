# Create a Pull Request

Create a pull request for the current branch with an auto-generated description.

## Instructions

1. Run `git status` to check for uncommitted changes - if any exist, ask the user if they want to commit first
2. Run `git branch --show-current` to get the current branch name
3. If on main/master, inform the user they need to be on a feature branch and stop
4. Run `git log main..HEAD` and `git diff main...HEAD` to understand all changes in this branch
5. Push the branch to origin if not already pushed: `git push -u origin <branch-name>`
6. Create the PR using `gh pr create` with:
   - A clear title summarizing the changes
   - A body with a Summary section (bullet points) and Test plan section
7. Return the PR URL to the user
