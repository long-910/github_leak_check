# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Documentation
- Add project background & motivation explaining why "Keep my email addresses private" alone is insufficient
- Add detailed 5-step remediation guide (profile fix, file fix, `.mailmap`, `git filter-repo`) in EN/ZH/JA

---

## [1.0.0] - 2026-03-29

### Added
- **`scan.py`** — Core scanner for GitHub commits, file contents, and user profiles
  - Scans `author.email` and `committer.email` across all repositories
  - Searches README, `package.json`, `pyproject.toml`, and other source files for email patterns
  - Checks public GitHub profile for exposed email
  - Flags any address that is not `@users.noreply.github.com` or other known-safe noreply patterns
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
  - Inputs: `github-token`, `username`, `target-emails`, `max-commits`, `include-forks`, `no-files`, `full-scan`, `max-rate-wait`, `output-dir`
  - Outputs: `status`, `leak-count`, `exit-code`
- **`.github/workflows/scan.yml`** — Automated daily scan workflow
  - Runs on push to `main`, daily at 03:00 UTC, and on manual trigger
  - Auto-cancels the run (instead of idling) when rate limited, saving CI minutes
  - Commits `results/summary.json` and `results/card.svg` back using noreply bot email
- **Incremental scanning** — Only checks commits made after the previous scan's timestamp (`since` field in `summary.json`)
- **Targeted email scanning** — `--email` CLI flag and `TARGET_EMAILS` Actions secret to watch specific addresses
- **Fork exclusion** — Forked repositories are skipped by default; opt-in with `--include-forks`
- **Rate limit handling** — Waits on `X-RateLimit-Reset`; aborts with exit code `2` if wait exceeds `--max-rate-wait` seconds
- **Output files**
  - `results/summary.json` — aggregated counts, no real emails (committed to repo)
  - `results/card.svg` — SVG status card (committed to repo)
  - `results/leaks.json` — full details with real addresses (gitignored, never committed)
- **Multilingual documentation** — README in English, Chinese (简体中文), and Japanese (日本語)
- **Windows support** — PowerShell and cmd.exe instructions documented in all READMEs

### Security
- `results/leaks.json` is gitignored so real email addresses are never committed
- GitHub Actions workflow uses `41898282+github-actions[bot]@users.noreply.github.com` — the repo's own commits are always clean

---

## [0.1.0] - 2026-03-29

### Added
- Initial project scaffold (`Initial commit`)

---

[Unreleased]: https://github.com/long-910/github_leak_check/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/long-910/github_leak_check/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/long-910/github_leak_check/releases/tag/v0.1.0
