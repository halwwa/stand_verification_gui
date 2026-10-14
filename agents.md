## Git workflow

- Keep commits small, focused, and logically atomic.
- Each commit should represent one coherent change.
- Avoid mixing refactoring with functional changes in the same commit.
- Use clear, descriptive commit messages.
- Do not amend, squash, rebase, or rewrite existing commits unless explicitly requested.
- Do not push to any remote repository unless explicitly requested by the user.
- Do not create pull requests unless explicitly requested.
- Do not change git remotes or repository settings.

When a task naturally consists of multiple independent steps, prefer
committing each completed step before moving to the next one.

Do not create a commit if the current changes are incomplete, broken,
or only an intermediate state that has no value on its own, unless
preserving that state is necessary for the task.