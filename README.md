# github-leak-check

**Language / 语言 / 言語:** English | [中文](README.zh.md) | [日本語](README.ja.md)

Scan GitHub commits, file contents, and user profiles for non-`noreply` email addresses — and display the result as a live badge on your GitHub profile.

<!-- Status card — auto-updated daily by GitHub Actions -->
<!-- Replace USERNAME with your GitHub username after forking -->
<!-- ![Scan Status](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg) -->

---

## What it does

1. **Commit scan** — checks every commit's `author.email` and `committer.email` across all your repos
2. **File scan** — searches README, package.json, pyproject.toml, etc. for email-like patterns
3. **Profile scan** — checks if your public GitHub profile has an email set
4. Flags anything that isn't a `@users.noreply.github.com` (or other bot/noreply) address

Results are stored as:
- `results/summary.json` — aggregated counts, **no real emails** (committed)
- `results/card.svg` — status card for embedding (committed)
- `results/leaks.json` — full details with real addresses (**gitignored, never committed**)

---

## Setup

### 1. Fork this repo

Fork to your own account so GitHub Actions runs under your identity.

### 2. Create a Personal Access Token

Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** and create a token with:

| Permission | Access |
|---|---|
| **Contents** | Read-only (all repos) |
| **Metadata** | Read-only |
| **Email addresses** | Read-only (under Account permissions) |

> Classic PAT: `repo` + `read:user` scopes work too.

### 3. Add the token as a repo secret

In your fork: **Settings → Secrets and variables → Actions → New repository secret**

- Name: `GH_PAT`
- Value: the token from step 2

### 4. Enable Actions

Go to the **Actions** tab in your fork and enable workflows if prompted.
The scan runs automatically every day at 03:00 UTC and on every push to `main`.
You can also trigger it manually from the Actions tab.

### 5. Embed the card in your profile README

Add this line to your `USERNAME/USERNAME` profile repository README:

```markdown
![Email Leak Scan](https://raw.githubusercontent.com/USERNAME/github_leak_check/main/results/card.svg)
```

Replace `USERNAME` with your actual GitHub username.

---

## Run locally

First, install dependencies:

```bash
pip install -r requirements.txt
```

### macOS / Linux

```bash
# Scan all non-noreply emails (replace with your username and token)
GH_PAT=ghp_... python scan.py YOUR_USERNAME --verbose

# Scan for a specific email address only
GH_PAT=ghp_... python scan.py YOUR_USERNAME --email your@example.com

# Scan for multiple specific addresses
GH_PAT=ghp_... python scan.py YOUR_USERNAME --email work@example.com --email personal@example.com

# Generate card from existing summary
python generate_card.py

# Scan without file content (faster)
GH_PAT=ghp_... python scan.py YOUR_USERNAME --no-files

# Increase commit depth (default: 500 per repo)
GH_PAT=ghp_... python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — PowerShell

```powershell
$env:GH_PAT = "ghp_..."

# Scan all non-noreply emails
python scan.py YOUR_USERNAME --verbose

# Scan for a specific email address only
python scan.py YOUR_USERNAME --email your@example.com

# Scan for multiple specific addresses
python scan.py YOUR_USERNAME --email work@example.com --email personal@example.com

# Generate card
python generate_card.py

# Scan without file content (faster)
python scan.py YOUR_USERNAME --no-files

# Increase commit depth
python scan.py YOUR_USERNAME --max-commits 2000
```

### Windows — Command Prompt (cmd.exe)

```cmd
set GH_PAT=ghp_...
python scan.py YOUR_USERNAME --verbose

python generate_card.py
```

---

## Fixing leaks

After running `scan.py`, use `fix.py` to replace leaked addresses.

```bash
python fix.py
```

It will prompt you for a replacement email for each leaked address.
The recommended format is `ID+USERNAME@users.noreply.github.com`
(find your numeric ID at `https://api.github.com/users/USERNAME`).

**What fix.py does:**

| Step | Action | Safe? |
|---|---|---|
| 1 | Generate/update `.mailmap` — rewrites `git log` display | ✅ Safe |
| 2 | Replace emails in local working-tree files | ✅ Safe |
| 3 | Rewrite git history with `git filter-repo` | ⚠️ Destructive — opt-in only |
| 4 | Print instructions for profile leaks | — Manual |

### Specify replacements upfront

```bash
# macOS / Linux
python fix.py --replace "old@example.com=12345+user@users.noreply.github.com"

# Windows — PowerShell
python fix.py --replace "old@example.com=12345+user@users.noreply.github.com"

# Windows — Command Prompt
python fix.py --replace "old@example.com=12345+user@users.noreply.github.com"
```

### Rewrite git history (destructive)

```bash
# Preview first
python fix.py --dry-run --rewrite

# Apply — cannot be undone without a backup
python fix.py --rewrite

# Then force-push
git push --force-with-lease origin main
```

> **Warning:** History rewrite requires all collaborators to re-clone or rebase.
> `git-filter-repo` is installed automatically via `pip install -r requirements.txt`.

---

## Safe email patterns (not flagged)

| Pattern | Example |
|---|---|
| `@users.noreply.github.com` | `12345+user@users.noreply.github.com` |
| `noreply@github.com` | `noreply@github.com` |
| `[bot]@` | `dependabot[bot]@users.noreply.github.com` |
| `@noreply.github.com` | `actions@noreply.github.com` |

Everything else is flagged as a potential leak.

---

## Rate limits

With a PAT the GitHub API allows **5,000 requests/hour**.
The scanner handles rate limiting automatically (waits on `X-RateLimit-Reset`).
Large accounts (100+ repos, thousands of commits) may need multiple runs or a higher `--max-commits` value spread across days.

---

## Self-check

This repo's own GitHub Actions workflow uses `41898282+github-actions[bot]@users.noreply.github.com` for all commits — it won't trigger its own scanner.

---

## License

MIT
