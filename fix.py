#!/usr/bin/env python3
"""
GitHub Email Leak Fixer
Replaces leaked email addresses found by scan.py.

Three fix strategies:
  1. .mailmap       — rewrites git log display only (safe, no history rewrite)
  2. File content   — patches emails in local working-tree files
  3. git filter-repo — rewrites actual git history (DESTRUCTIVE, opt-in)

Profile leaks always require a manual fix in GitHub Settings.

Usage:
    python fix.py [--replace OLD=NEW] [--dry-run] [--rewrite]
    python fix.py --help
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


# ── Load leaks ─────────────────────────────────────────────────────────────────

def load_leaks(path: str) -> tuple[dict, list]:
    p = Path(path)
    if not p.exists():
        _die(f"{path} not found. Run scan.py first.")
    data = json.loads(p.read_text(encoding="utf-8"))
    # Support both {summary, leaks} and flat list formats
    if isinstance(data, list):
        return {}, data
    return data.get("summary", {}), data.get("leaks", [])


# ── Replacement collection ─────────────────────────────────────────────────────

def collect_replacements(
    leaks: list,
    cli_map: dict[str, str],
    username: str,
) -> dict[str, str]:
    """
    Build a mapping of { leaked_email: replacement_email }.
    Uses --replace values where provided; prompts interactively for the rest.
    """
    unique_emails: dict[str, str] = {}   # email → name (first seen)
    for leak in leaks:
        email = leak.get("email", "")
        if email and leak["surface"] != "profile":
            unique_emails.setdefault(email, leak.get("name", ""))
    profile_emails = [l["email"] for l in leaks if l["surface"] == "profile" and l.get("email")]

    replacements: dict[str, str] = dict(cli_map)

    all_emails = list(unique_emails.keys()) + [e for e in profile_emails if e not in unique_emails]

    need_input = [e for e in all_emails if e not in replacements]
    if not need_input:
        return replacements

    id_hint = f"(find yours: https://api.github.com/users/{username} → 'id')" if username else ""
    suggestion = f"ID+{username}@users.noreply.github.com" if username else "ID+USERNAME@users.noreply.github.com"

    print(f"\nFor each leaked email, enter the safe replacement address.")
    print(f"GitHub noreply format: {suggestion}")
    if id_hint:
        print(f"  {id_hint}")
    print()

    for email in need_input:
        name = unique_emails.get(email, "")
        label = f"{email}" + (f"  (git name: {name})" if name else "")
        val = input(f"  Replace  {label}\n  → ").strip()
        if not val:
            print("  Skipped.")
        else:
            replacements[email] = val

    return replacements


# ── Fix: .mailmap ──────────────────────────────────────────────────────────────

def fix_mailmap(
    leaks: list,
    replacements: dict[str, str],
    mailmap_path: str = ".mailmap",
    dry_run: bool = False,
) -> bool:
    commit_leaks = [l for l in leaks if l["surface"].startswith("commit_")]
    if not commit_leaks:
        return False

    p = Path(mailmap_path)
    existing_text = p.read_text(encoding="utf-8") if p.exists() else ""
    existing_lines = set(existing_text.splitlines())

    new_lines: list[str] = []
    seen: set[str] = set()

    for leak in commit_leaks:
        old_email = leak["email"]
        new_email = replacements.get(old_email)
        if not new_email or old_email == new_email:
            continue
        name = leak.get("name", "").strip()
        key = f"{old_email}→{new_email}"
        if key in seen:
            continue
        seen.add(key)

        # .mailmap format: [Proper Name] <canonical@email> [<old@email>]
        line = f"{name} <{new_email}> <{old_email}>" if name else f"<{new_email}> <{old_email}>"
        if line not in existing_lines:
            new_lines.append(line)

    if not new_lines:
        _info("mailmap", "No new entries needed.")
        return False

    if dry_run:
        _info("mailmap", f"[DRY RUN] Would add {len(new_lines)} line(s) to {mailmap_path}:")
        for line in new_lines:
            print(f"    {line}")
        return True

    content = existing_text.rstrip("\n")
    if content:
        content += "\n"
    content += "\n".join(new_lines) + "\n"
    p.write_text(content, encoding="utf-8")
    _ok("mailmap", f"Updated {mailmap_path} — {len(new_lines)} mapping(s) added.")
    return True


# ── Fix: file content ──────────────────────────────────────────────────────────

def fix_files(
    leaks: list,
    replacements: dict[str, str],
    dry_run: bool = False,
) -> list[Path]:
    file_leaks = [l for l in leaks if l["surface"] == "file_content"]
    if not file_leaks:
        return []

    # Group by file path (relative to cwd)
    by_file: dict[str, set[str]] = defaultdict(set)
    for leak in file_leaks:
        fpath = leak.get("file", "")
        email = leak.get("email", "")
        if fpath and email and email in replacements:
            by_file[fpath].add(email)

    changed: list[Path] = []
    for fpath_str, emails in by_file.items():
        p = Path(fpath_str)
        if not p.exists():
            _warn("files", f"Not found locally: {fpath_str}  (clone the repo first)")
            continue

        content = p.read_text(encoding="utf-8", errors="replace")
        new_content = content
        for email in emails:
            new_email = replacements[email]
            new_content = new_content.replace(email, new_email)

        if new_content == content:
            continue

        if dry_run:
            for email in emails:
                _info("files", f"[DRY RUN] {fpath_str}: {email} → {replacements[email]}")
        else:
            p.write_text(new_content, encoding="utf-8")
            for email in emails:
                _ok("files", f"{fpath_str}: {email} → {replacements[email]}")
        changed.append(p)

    return changed


# ── Fix: git filter-repo ───────────────────────────────────────────────────────

def check_filter_repo() -> bool:
    return shutil.which("git-filter-repo") is not None or _git_filter_repo_available()


def _git_filter_repo_available() -> bool:
    try:
        result = subprocess.run(
            ["git", "filter-repo", "--version"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def rewrite_history(mailmap_path: str = ".mailmap", dry_run: bool = False) -> bool:
    if not Path(mailmap_path).exists():
        _warn("rewrite", f"{mailmap_path} not found — generate it first (remove --rewrite to do that).")
        return False

    if not check_filter_repo():
        _warn("rewrite", "git-filter-repo not found. Install it:")
        print("      pip install git-filter-repo")
        print("    or: https://github.com/newren/git-filter-repo#how-do-i-install-it")
        return False

    # Verify we're inside a git repo
    result = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True)
    if result.returncode != 0:
        _warn("rewrite", "Not inside a git repository.")
        return False

    cmd = ["git", "filter-repo", "--mailmap", mailmap_path, "--force"]
    if dry_run:
        _info("rewrite", f"[DRY RUN] Would run: {' '.join(cmd)}")
        return True

    print(f"\n  Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode == 0:
        _ok("rewrite", "History rewritten successfully.")
        print()
        print("  IMPORTANT: You must force-push to update the remote:")
        print("    git push --force-with-lease origin main")
        print()
        print("  WARNING: All collaborators must re-clone or rebase their local copies.")
        return True
    else:
        _warn("rewrite", f"git filter-repo exited with code {proc.returncode}.")
        return False


# ── Instructions ───────────────────────────────────────────────────────────────

def print_repo_instructions(leaks: list, replacements: dict[str, str]):
    """Print per-repo git filter-repo commands for repos not fixed locally."""
    commit_leaks = [l for l in leaks if l["surface"].startswith("commit_")]
    if not commit_leaks:
        return

    repos: dict[str, set[str]] = defaultdict(set)
    for leak in commit_leaks:
        repo = leak.get("repo", "")
        email = leak.get("email", "")
        if repo and email and email in replacements:
            repos[repo].add(email)

    if not repos:
        return

    print("\n" + "─" * 60)
    print("  Repos requiring history rewrite")
    print("  (run these commands after cloning each repo)")
    print("─" * 60)
    for repo, emails in repos.items():
        print(f"\n  # {repo}")
        print(f"  git clone https://github.com/{repo}.git")
        print(f"  cd {repo.split('/')[-1]}")
        for email in emails:
            new_email = replacements[email]
            print(f"  # {email} → {new_email}")
        print(f"  # (update .mailmap then run:)")
        print(f"  git filter-repo --mailmap .mailmap --force")
        print(f"  git push --force-with-lease origin main")


def print_profile_instructions(leaks: list):
    profile_leaks = [l for l in leaks if l["surface"] == "profile"]
    if not profile_leaks:
        return

    print("\n" + "─" * 60)
    print("  Profile email — manual fix required")
    print("─" * 60)
    print("  GitHub Settings → Public profile → Email")
    print("  Uncheck 'Display email publicly' or clear the email field.")
    print("  https://github.com/settings/profile")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ok(tag: str, msg: str):
    print(f"  \033[32m✓\033[0m  [{tag}] {msg}")

def _info(tag: str, msg: str):
    print(f"  \033[34m·\033[0m  [{tag}] {msg}")

def _warn(tag: str, msg: str):
    print(f"  \033[33m!\033[0m  [{tag}] {msg}", file=sys.stderr)

def _die(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fix leaked email addresses found by scan.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive — prompts for replacement email
  python fix.py

  # Specify replacement upfront (can be repeated)
  python fix.py --replace "old@example.com=12345+user@users.noreply.github.com"

  # Also rewrite local git history (DESTRUCTIVE — requires git-filter-repo)
  python fix.py --rewrite

  # Preview changes without applying
  python fix.py --dry-run
        """,
    )
    parser.add_argument(
        "--leaks",
        default="results/leaks.json",
        metavar="FILE",
        help="Path to leaks.json from scan.py (default: results/leaks.json)",
    )
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Email replacement pair, e.g. old@example.com=ID+user@users.noreply.github.com",
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Rewrite git history with git filter-repo (DESTRUCTIVE — cannot be undone without backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without applying anything",
    )
    parser.add_argument(
        "--mailmap",
        default=".mailmap",
        metavar="FILE",
        help="Path to .mailmap file (default: .mailmap)",
    )
    args = parser.parse_args()

    # Parse --replace pairs
    cli_map: dict[str, str] = {}
    for pair in args.replace:
        if "=" not in pair:
            _die(f"--replace value must be OLD=NEW, got: {pair!r}")
        old, _, new = pair.partition("=")
        cli_map[old.strip()] = new.strip()

    # Load leaks
    summary, leaks = load_leaks(args.leaks)
    if not leaks:
        print("No leaks found in leaks.json — nothing to fix.")
        return

    username = summary.get("username", "")

    # Group leak counts
    by_surface: dict[str, int] = defaultdict(int)
    for l in leaks:
        by_surface[l["surface"]] += 1

    print(f"\nLeaks loaded from {args.leaks}:")
    for surface, count in sorted(by_surface.items()):
        print(f"  {surface}: {count}")

    if args.dry_run:
        print("\n  [DRY RUN mode — no files will be modified]\n")

    if args.rewrite:
        print("\n  \033[31m⚠  --rewrite: git history will be permanently modified.\033[0m")
        confirm = input("  Type 'yes' to continue: ").strip()
        if confirm.lower() != "yes":
            print("  Aborted.")
            return

    # Collect replacements
    replacements = collect_replacements(leaks, cli_map, username)
    if not any(replacements.values()):
        print("\nNo replacements provided — nothing to do.")
        return

    print()

    # ── 1. .mailmap ────────────────────────────────────────────────────────────
    print("── Step 1: .mailmap ───────────────────────────────────────")
    fix_mailmap(leaks, replacements, args.mailmap, dry_run=args.dry_run)

    # ── 2. File content ────────────────────────────────────────────────────────
    print("\n── Step 2: File content ───────────────────────────────────")
    changed = fix_files(leaks, replacements, dry_run=args.dry_run)
    if not changed:
        _info("files", "No local file content to fix (or no matching files found).")

    # ── 3. Git history rewrite ─────────────────────────────────────────────────
    if args.rewrite:
        print("\n── Step 3: Git history rewrite ────────────────────────────")
        rewrite_history(args.mailmap, dry_run=args.dry_run)
    else:
        print("\n── Step 3: Git history rewrite ────────────────────────────")
        _info(
            "rewrite",
            "Skipped. .mailmap rewrites git log display only.\n"
            "           To actually rewrite history, re-run with --rewrite\n"
            "           (requires git-filter-repo: pip install git-filter-repo)",
        )
        print_repo_instructions(leaks, replacements)

    # ── 4. Profile ─────────────────────────────────────────────────────────────
    print("\n── Step 4: Profile email ──────────────────────────────────")
    profile_leaks = [l for l in leaks if l["surface"] == "profile"]
    if profile_leaks:
        print_profile_instructions(leaks)
    else:
        _info("profile", "No profile leak.")

    # ── Summary ────────────────────────────────────────────────────────────────
    if not args.dry_run and changed:
        print("\n── Next steps ─────────────────────────────────────────────")
        print("  Stage and commit the fixed files:")
        file_list = " ".join(str(f) for f in changed[:5])
        if len(changed) > 5:
            file_list += " ..."
        if Path(args.mailmap).exists():
            print(f"    git add {args.mailmap} {file_list}")
        else:
            print(f"    git add {file_list}")
        print('    git commit -m "fix: replace leaked email addresses"')
        print("    git push")


if __name__ == "__main__":
    main()
