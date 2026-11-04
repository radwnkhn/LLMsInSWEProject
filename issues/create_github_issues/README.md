# Create the GitHub issues

Creates 30 issues (20 Alpha, 10 Beta), plus their labels and milestones, on
radwnkhn/LLMsInSWEProject. Safe to run twice: issues that already exist are skipped.

1. Install the GitHub CLI if you don't have it: `brew install gh`
2. Sign in: `gh auth login` (pick GitHub.com, then log in with your browser).
   Your account needs write access to the repo.
3. In this folder, run:

       python3 create_issues.py radwnkhn/LLMsInSWEProject

   To preview without creating anything, add `--dry-run`.
