#!/usr/bin/env python3
"""
GitHub Email Leak Scanner
Detects non-noreply email addresses in GitHub commits, file contents, and profiles.

Usage:
    python scan.py [USERNAME]
    python scan.py --help

Environment variables:
    GH_PAT           Personal Access Token (repo + read:user scopes)
    GITHUB_TOKEN     Fallback token (limited to current repo)
    GITHUB_USERNAME  Target username (used in GitHub Actions)
"""

import base64
import json
import os
import re
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

import requests

# ── Email patterns ─────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# Emails matching ANY of these patterns are considered safe (not a leak)
SAFE_PATTERNS = [
    re.compile(r"@users\.noreply\.github\.com$", re.I),
    re.compile(r"^noreply@github\.com$", re.I),
    re.compile(r"@noreply\.github\.com$", re.I),
    re.compile(r"\[bot\]@", re.I),
    re.compile(r"^github-actions", re.I),
    re.compile(r"^dependabot", re.I),
    re.compile(r"^action@github\.com$", re.I),
]

# File extensions to skip during content scanning (binary / non-text)
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    ".pyc", ".pyo",
}

# Max file size to scan for emails (bytes)
MAX_FILE_BYTES = 500_000


def is_safe(email: str) -> bool:
    """Return True if the email is a known safe/noreply/bot address."""
    return any(p.search(email) for p in SAFE_PATTERNS)


def redact(email: str) -> str:
    """Partially redact an email for safe display in logs/summaries."""
    try:
        user, domain = email.rsplit("@", 1)
        masked = user[0] + "*" * max(len(user) - 2, 1) + user[-1] if len(user) > 2 else user[0] + "*"
        return f"{masked}@{domain}"
    except ValueError:
        return "***@***"


# ── GitHub API client ──────────────────────────────────────────────────────────

class GitHubClient:
    API_BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, url: str, params: Optional[dict] = None) -> dict | list:
        if not url.startswith("http"):
            url = self.API_BASE + url
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 429 or (
                resp.status_code == 403
                and resp.headers.get("X-RateLimit-Remaining") == "0"
            ):
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 0) + 2
                _log(f"  Rate limited. Waiting {wait:.0f}s...")
                time.sleep(wait)
                continue

            if resp.status_code == 404:
                return {}
            if resp.status_code == 409:  # empty repo
                return []

            resp.raise_for_status()
            return resp.json()

        raise RuntimeError(f"Failed after 3 attempts: {url}")

    def paginate(self, path: str, params: Optional[dict] = None) -> Generator:
        """Yield all items across all pages of a list endpoint."""
        params = dict(params or {})
        params["per_page"] = 100
        url = self.API_BASE + path if not path.startswith("http") else path
        while url:
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code in (404, 409):
                return
            if resp.status_code == 429 or (
                resp.status_code == 403
                and resp.headers.get("X-RateLimit-Remaining") == "0"
            ):
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                time.sleep(max(reset - time.time(), 0) + 2)
                continue
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                yield from data
            elif isinstance(data, dict) and "items" in data:
                yield from data["items"]
            # Follow Link header for next page
            link = resp.headers.get("Link", "")
            next_url = None
            for part in link.split(","):
                part = part.strip()
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
            url = next_url
            params = {}  # params are already encoded in next_url

    def get_user(self, username: str) -> dict:
        return self._get(f"/users/{username}")

    def get_repos(self, username: str) -> Generator:
        yield from self.paginate(f"/users/{username}/repos", {"type": "owner"})

    def get_commits(self, repo: str) -> Generator:
        yield from self.paginate(f"/repos/{repo}/commits")

    def get_tree(self, repo: str, sha: str) -> list:
        data = self._get(f"/repos/{repo}/git/trees/{sha}", {"recursive": "1"})
        return data.get("tree", []) if isinstance(data, dict) else []

    def get_blob(self, repo: str, sha: str) -> Optional[str]:
        data = self._get(f"/repos/{repo}/git/blobs/{sha}")
        if not isinstance(data, dict):
            return None
        size = data.get("size", 0)
        if size > MAX_FILE_BYTES:
            return None
        encoding = data.get("encoding")
        content = data.get("content", "")
        if encoding == "base64":
            try:
                raw = base64.b64decode(content)
                # Quick binary check
                if b"\x00" in raw[:512]:
                    return None
                return raw.decode("utf-8", errors="replace")
            except Exception:
                return None
        return content if isinstance(content, str) else None


# ── Scanner ─────────────────────────────────────────────────────────────────────

class LeakScanner:
    def __init__(self, client: GitHubClient, max_commits: int = 500, scan_files: bool = True):
        self.client = client
        self.max_commits = max_commits
        self.scan_files = scan_files
        self.leaks: list[dict] = []
        self.stats = {
            "repos_scanned": 0,
            "commits_scanned": 0,
            "files_scanned": 0,
        }

    def _add_leak(self, entry: dict):
        self.leaks.append(entry)
        _log(f"    ⚠  [{entry['surface']}] {entry['redacted']}")

    def scan_profile(self, username: str):
        _log(f"Checking profile @{username}...")
        user = self.client.get_user(username)
        email = (user.get("email") or "").strip()
        if email and not is_safe(email):
            self._add_leak({
                "surface": "profile",
                "location": f"https://github.com/{username}",
                "email": email,
                "redacted": redact(email),
            })

    def scan_commits(self, repo_name: str):
        count = 0
        seen: set[str] = set()
        for commit in self.client.get_commits(repo_name):
            if count >= self.max_commits:
                break
            count += 1
            self.stats["commits_scanned"] += 1
            c = commit.get("commit", {})
            sha = commit.get("sha", "")[:7]

            for role in ("author", "committer"):
                git_data = c.get(role) or {}
                email = (git_data.get("email") or "").strip()
                name = (git_data.get("name") or "").strip()

                if not email or is_safe(email):
                    continue

                key = f"{repo_name}:{role}:{email}"
                if key in seen:
                    continue
                seen.add(key)

                self._add_leak({
                    "surface": f"commit_{role}",
                    "repo": repo_name,
                    "sha": sha,
                    "email": email,
                    "redacted": redact(email),
                    "name": name,
                })

    def scan_file_contents(self, repo_name: str, default_branch: str):
        tree = self.client.get_tree(repo_name, default_branch)
        seen: set[str] = set()

        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            ext = Path(path).suffix.lower()
            if ext in BINARY_EXTENSIONS:
                continue

            blob_sha = item.get("sha", "")
            content = self.client.get_blob(repo_name, blob_sha)
            if content is None:
                continue

            self.stats["files_scanned"] += 1
            for match in EMAIL_RE.finditer(content):
                email = match.group()
                if is_safe(email):
                    continue
                key = f"{repo_name}:{path}:{email}"
                if key in seen:
                    continue
                seen.add(key)

                # Find line number
                line_no = content[: match.start()].count("\n") + 1

                self._add_leak({
                    "surface": "file_content",
                    "repo": repo_name,
                    "file": path,
                    "line": line_no,
                    "email": email,
                    "redacted": redact(email),
                })

    def run(self, username: str) -> dict:
        self.scan_profile(username)

        repos = list(self.client.get_repos(username))
        _log(f"Found {len(repos)} repos owned by @{username}")

        for i, repo in enumerate(repos, 1):
            full_name = repo["full_name"]
            branch = repo.get("default_branch") or "main"
            is_fork = repo.get("fork", False)
            _log(f"  [{i}/{len(repos)}] {full_name}{'  (fork)' if is_fork else ''}")

            self.stats["repos_scanned"] += 1
            self.scan_commits(full_name)
            if self.scan_files:
                self.scan_file_contents(full_name, branch)

        # Build summary (no real emails)
        leak_by_surface: dict[str, int] = {}
        for leak in self.leaks:
            leak_by_surface[leak["surface"]] = leak_by_surface.get(leak["surface"], 0) + 1

        summary = {
            "username": username,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "repos_scanned": self.stats["repos_scanned"],
            "commits_scanned": self.stats["commits_scanned"],
            "files_scanned": self.stats["files_scanned"],
            "leak_count": len(self.leaks),
            "leak_by_surface": leak_by_surface,
            "status": "CLEAN" if not self.leaks else "LEAKS_FOUND",
        }

        return {"summary": summary, "leaks": self.leaks}


# ── Utilities ──────────────────────────────────────────────────────────────────

_VERBOSE = False

def _log(msg: str):
    if _VERBOSE:
        print(msg, file=sys.stderr)


def _print(msg: str):
    print(msg, file=sys.stderr)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    global _VERBOSE

    parser = argparse.ArgumentParser(
        description="Scan a GitHub user's repos for non-noreply email addresses.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Secrets / env vars:
  GH_PAT           Personal Access Token (repo + read:user scopes) [recommended]
  GITHUB_TOKEN     Fallback token (limited scope)
  GITHUB_USERNAME  Target username when not passed as argument

Output files:
  results/summary.json   Aggregated counts, no real emails. Committed to git.
  results/leaks.json     Full details with real emails. Gitignored!
        """,
    )
    parser.add_argument("username", nargs="?", help="GitHub username to scan")
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN"),
        metavar="TOKEN",
        help="GitHub token (default: $GH_PAT or $GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=500,
        metavar="N",
        help="Max commits to scan per repo (default: 500)",
    )
    parser.add_argument(
        "--no-files",
        action="store_true",
        help="Skip file content scanning (faster)",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        metavar="DIR",
        help="Directory for output files (default: results)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _VERBOSE = args.verbose

    username = (
        args.username
        or os.environ.get("GITHUB_USERNAME")
        or os.environ.get("GITHUB_ACTOR")
    )
    if not username:
        parser.error(
            "GitHub username required: pass as argument or set GITHUB_USERNAME env var"
        )

    if not args.token:
        _print("WARNING: No token provided. Rate limit is 60 req/hr. Large repos may fail.")

    _print(f"Scanning @{username} for email leaks...")

    client = GitHubClient(token=args.token)
    scanner = LeakScanner(
        client,
        max_commits=args.max_commits,
        scan_files=not args.no_files,
    )

    try:
        result = scanner.run(username)
    except Exception as exc:
        _print(f"ERROR: {exc}")
        result = {
            "summary": {
                "username": username,
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "repos_scanned": 0,
                "commits_scanned": 0,
                "files_scanned": 0,
                "leak_count": 0,
                "leak_by_surface": {},
                "status": "ERROR",
                "error": str(exc),
            },
            "leaks": [],
        }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # leaks.json - gitignored, contains real emails
    leaks_path = out_dir / "leaks.json"
    leaks_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # summary.json - safe to commit, no real emails
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(result["summary"], indent=2, ensure_ascii=False), encoding="utf-8")

    s = result["summary"]
    status_icon = "✅" if s["status"] == "CLEAN" else ("🚨" if s["status"] == "LEAKS_FOUND" else "⚠️")
    _print(f"\n{status_icon} Status: {s['status']}")
    _print(f"   Repos scanned:   {s['repos_scanned']}")
    _print(f"   Commits scanned: {s['commits_scanned']}")
    _print(f"   Files scanned:   {s['files_scanned']}")
    _print(f"   Leaks found:     {s['leak_count']}")

    if result["leaks"]:
        _print("\nLeaks detected (redacted):")
        for leak in result["leaks"]:
            loc = leak.get("repo") or leak.get("location", "?")
            _print(f"  [{leak['surface']}] {loc}: {leak['redacted']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
