## Installation options

### Project-level (shared)

This skill is stored under:
- `.cursor/skills/doc-first-workflow/`

Anyone who clones the repo can use it as a project skill.

### Personal-level (reusable across projects)

Copy the skill directory to:
- `~/.cursor/skills/doc-first-workflow/`

On Windows, `~` typically resolves to `C:\Users\<you>`.

You can use the helper script in `scripts/install_personal.ps1`.

## Customization

- **Plans root**: The default examples use `metadata/plans/`. If a different plans root is desired, update the SKILL.md rules and templates accordingly.
- **Fast-track criteria**: Adjust the tiny bugfix gate if your team prefers stricter/looser thresholds.

