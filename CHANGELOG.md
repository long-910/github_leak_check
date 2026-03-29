# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-03-29

### Added

- **`scan.py`** — Core scanner for GitHub commits, file contents, and user profiles
  - Scans `author.email` and `committer.email` across all repositories
  - Searches README, `package.json`, `pyproject.toml`, and other source files for email patterns
  - Checks public GitHub profile for exposed email
  - Flags any address that is not `@users.noreply.github.com` or other known-safe noreply patterns
  - Incremental scanning — only checks commits since the previous scan's timestamp
  - Exit codes: `0` = clean, `1` = leaks found, `2` = rate limited
- **`generate_card.py`** — SVG status card generator embeddable in GitHub profile README
  - Statuses: `CLEAN` (green), `LEAKS_FOUND` (red + pulse animation), `RATE_LIMITED` (purple), `ERROR` (orange)
  - No JS, no `foreignObject`, no external fonts — fully GitHub-safe
- **`fix.py`** — Interactive email replacement tool
  - Generates `.mailmap` to remap displayed email in `git log` (safe, no history rewrite)
  - Replaces emails in working-tree source files
  - Optional `--rewrite` flag to permanently rewrite history with `git filter-repo`
  - `--dry-run` flag to preview changes without applying
- **`action.yml`** — Composite GitHub Action published to the Actions Marketplace
  - Inputs: `github-token`, `username`, `target-emails`, `max-commits`, `include-forks`, `no-files`, `full-scan`, `reset-commits`, `max-rate-wait`, `output-dir`
  - Outputs: `status`, `leak-count`, `exit-code`
- **`.github/workflows/scan.yml`** — Automated daily scan workflow
  - Runs on push to `main`, daily at 03:00 UTC, and on manual trigger
  - `workflow_dispatch` inputs: `full-scan`, `reset-commits` for on-demand control
  - Auto-cancels the run when rate limited to avoid wasting CI minutes
  - Commits `results/summary.json` and `results/card.svg` back using noreply bot email
- **Accumulated commit leak tracking** — Commit leak fingerprints (SHA-256, no real emails) are persisted across incremental runs so old leaks are never silently lost
- **Fork exclusion** — Forked repositories are skipped by default; opt-in with `--include-forks`
- **Rate limit handling** — Waits on `X-RateLimit-Reset`; aborts with exit code `2` if wait exceeds `--max-rate-wait`
- **Multilingual documentation** — README in English (default), 中文, 日本語 with badges, Mermaid flow diagrams, and remediation guide
- **Windows support** — PowerShell and cmd.exe run instructions documented

### Security

- `results/leaks.json` is gitignored — real email addresses are never committed
- `results/summary.json` stores only counts and email-free fingerprints — safe to commit
- GitHub Actions workflow uses `41898282+github-actions[bot]@users.noreply.github.com` — the repo's own commits never trigger the scanner
- `TARGET_EMAILS` secret is never written to `summary.json` (only the count is stored)

---

[0.1.0]: https://github.com/long-910/github_leak_check/releases/tag/v0.1.0
