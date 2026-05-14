# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

Build a tool for users of `https://7080.wang` that supports searching, single-video downloading, and batch downloading. Use the drama "遮天" as the test target during development:
`https://7080.wang/so.html?id=0&wd=%E9%81%AE%E5%A4%A9`

The repository is currently a fresh project — only `prompt.md` (workflow spec) exists. Source code, `plan.md`, and `README.md` will be created during development.

## Repository Rules (from `prompt.md`)

- **Never modify `prompt.md`** — it is the human-authored instruction file.
- **Always develop on `main`** — do not branch for new versions.
- Run all `gh` commands from the repo root.
- Split documentation into separate Markdown files by chapter/topic (do not put everything in one large doc).
- Never commit secrets/keys; maintain a sensible `.gitignore`.

## Required Per-Task Workflow

Every task must follow this iteration loop. Do not skip steps.

### 1. Plan — decide the next version's scope

Pick the version type using this priority order:

1. If the planned tasks in `plan.md` are all complete → **stop the task immediately**.
2. Else if there are open GitHub issues (check via `gh issue list --state open --limit 3 --search "sort:created-desc"`) → plan a **PATCH** release that fixes them.
3. Else → plan a **MINOR** release implementing the next unfinished feature from `plan.md`.

Record the new version's goal and task list in `plan.md`. Example progression: `0.2.0 → 0.2.1 (issue fix) → 0.3.0 → 0.4.0 → 1.0.0 (all done)`.

### 2. Develop & Review

- Bump the version number everywhere it appears.
- Implement the items listed for this version in `plan.md`.
- Review the work, including core functionality and a test report.
- Commit in small, well-scoped chunks — one chapter/section per commit. Stage exactly the right files (no missing, no extras).

### 3. Release

- Create a Git tag with the new version and push it to GitHub.
- Publish a GitHub Release for that tag.

### 4. Documentation

- Update `plan.md` with progress and status.
- Refresh `README.md` with the latest project overview.
- `README.md` must keep at most the **5 most recent version** sections; older entries get merged/compressed into a single combined section.

### 5. Issue Closure

- Close resolved issues. Reply on each closed issue (in Markdown) stating which version contains the fix, link the release download, and ask the user to verify.

## Commit Conventions

- Format: Conventional Commits — `<type>(<scope>): <subject>`. Allowed types: `feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert`.
- Subject line ≤ 72 characters.
- Write commit messages in **Simplified Chinese**.
- **Do not** add `Signed-off-by`, `Co-authored-by`, "Written by Claude", "AI-generated", or any AI-attribution text. Use the default git user as the sole author.
- Output the commit message directly — no preamble like "好的, 这是提交信息……".

## Versioning

Semantic Versioning `MAJOR.MINOR.PATCH`:

- **MAJOR** — breaking changes
- **MINOR** — new backward-compatible features
- **PATCH** — bug fixes / refactors, backward-compatible

## Target Audience

End users of `https://7080.wang`. Frame UX, language (Simplified Chinese), and feature decisions accordingly.
