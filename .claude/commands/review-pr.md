# Review a Pull Request

Review a pull request by number or URL.

## Instructions

1. Get the PR identifier from the argument: $ARGUMENTS
2. If no argument provided, run `gh pr list` to show open PRs and ask user which to review
3. Use `gh pr view <number> --json title,body,author,state,additions,deletions,files` to get PR details
4. Use `gh pr diff <number>` to get the full diff
5. Review the changes and provide:
   - Summary of what the PR does
   - List of files changed
   - Any potential issues or concerns
   - Suggestions for improvement if applicable
6. Ask the user if they want to approve, request changes, or comment
