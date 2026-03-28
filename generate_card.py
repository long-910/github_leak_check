#!/usr/bin/env python3
"""
Generate an SVG status card from scan summary.
Safe for embedding on GitHub profile (no JS, no foreignObject, no external resources).

Usage:
    python generate_card.py [--summary results/summary.json] [--output results/card.svg]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── SVG template ───────────────────────────────────────────────────────────────
# Uses only: rect, text, line, circle, defs, linearGradient, animate
# No: foreignObject, script, external fonts, emoji (uses Unicode symbols instead)

SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="460" height="210" viewBox="0 0 460 210"
     role="img" aria-label="GitHub Email Leak Scan Status">
  <title>GitHub Email Leak Scan</title>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="460" y2="210" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0d1117"/>
      <stop offset="100%" stop-color="#161b22"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="460" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="{color_start}"/>
      <stop offset="100%" stop-color="{color_end}"/>
    </linearGradient>
  </defs>

  <!-- Card background -->
  <rect width="460" height="210" rx="10" fill="url(#bg)" stroke="#30363d" stroke-width="1"/>

  <!-- Top accent bar -->
  <rect width="460" height="4" rx="10" fill="url(#accent)"/>
  <rect y="2" width="460" height="3" fill="#0d1117"/>

  <!-- Title -->
  <text x="20" y="36"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="15" font-weight="600" fill="#e6edf3">
    &#128269; GitHub Email Leak Scan
  </text>

  <!-- Status badge -->
  <rect x="20" y="48" width="{badge_w}" height="24" rx="5"
        fill="{badge_fill}" opacity="0.12"/>
  <rect x="20" y="48" width="{badge_w}" height="24" rx="5"
        fill="none" stroke="{badge_stroke}" stroke-width="1"/>
  <circle cx="35" cy="60" r="4" fill="{badge_stroke}">
    {pulse_anim}
  </circle>
  <text x="46" y="65"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="12" font-weight="700" fill="{badge_stroke}">
    {status_label}
  </text>

  <!-- Divider -->
  <line x1="20" y1="86" x2="440" y2="86" stroke="#21262d" stroke-width="1"/>

  <!-- Stats row -->
  <!-- Repos -->
  <text x="20" y="116"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="26" font-weight="700" fill="#e6edf3">{repos}</text>
  <text x="20" y="133"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="11" fill="#8b949e">repos scanned</text>

  <!-- Commits -->
  <text x="150" y="116"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="26" font-weight="700" fill="#e6edf3">{commits}</text>
  <text x="150" y="133"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="11" fill="#8b949e">commits checked</text>

  <!-- Leaks count -->
  <text x="300" y="116"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="26" font-weight="700" fill="{leaks_color}">{leaks}</text>
  <text x="300" y="133"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="11" fill="#8b949e">leaks found</text>

  <!-- Divider -->
  <line x1="20" y1="150" x2="440" y2="150" stroke="#21262d" stroke-width="1"/>

  <!-- Breakdown row -->
  <text x="20" y="170"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="11" fill="#8b949e">Profile: {leak_profile}  &#183;  Commits: {leak_commits}  &#183;  Files: {leak_files}</text>

  <!-- Footer -->
  <text x="20" y="196"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="11" fill="#484f58">Last scan: {scanned_at}</text>
  <text x="440" y="196"
        font-family="&apos;Segoe UI&apos;, system-ui, -apple-system, sans-serif"
        font-size="11" fill="#484f58" text-anchor="end">Auto-updated by GitHub Actions</text>
</svg>
"""

PULSE_ANIM = """\
    <animate attributeName="opacity" values="1;0.3;1" dur="2s" repeatCount="indefinite"/>"""


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def generate(summary: dict) -> str:
    status = summary.get("status", "ERROR")
    leaks = summary.get("leak_count", 0)
    repos = summary.get("repos_scanned", 0)
    commits = summary.get("commits_scanned", 0)
    by_surface = summary.get("leak_by_surface", {})
    scanned_raw = summary.get("scanned_at", "")

    leak_profile = by_surface.get("profile", 0)
    leak_commits = sum(v for k, v in by_surface.items() if k.startswith("commit_"))
    leak_files = by_surface.get("file_content", 0)

    try:
        dt = datetime.fromisoformat(scanned_raw.replace("Z", "+00:00"))
        scanned_at = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        scanned_at = scanned_raw[:10] if scanned_raw else "N/A"

    if status == "CLEAN":
        color_start = "#2ea043"
        color_end   = "#3fb950"
        badge_fill   = "#2ea043"
        badge_stroke = "#3fb950"
        leaks_color  = "#3fb950"
        status_label = "CLEAN  \u2713"
        pulse_anim   = ""
    elif status == "LEAKS_FOUND":
        color_start = "#da3633"
        color_end   = "#f85149"
        badge_fill   = "#da3633"
        badge_stroke = "#f85149"
        leaks_color  = "#f85149"
        status_label = f"LEAKS FOUND  \u26a0"
        pulse_anim   = PULSE_ANIM
    else:  # ERROR or UNKNOWN
        color_start = "#9e6a03"
        color_end   = "#d29922"
        badge_fill   = "#9e6a03"
        badge_stroke = "#d29922"
        leaks_color  = "#d29922"
        status_label = "SCAN ERROR"
        pulse_anim   = ""

    # Estimate badge width from label length
    badge_w = len(status_label) * 9 + 30

    return SVG.format(
        color_start=color_start,
        color_end=color_end,
        badge_fill=badge_fill,
        badge_stroke=badge_stroke,
        badge_w=badge_w,
        pulse_anim=pulse_anim,
        status_label=status_label,
        leaks_color=leaks_color,
        repos=fmt_num(repos),
        commits=fmt_num(commits),
        leaks=fmt_num(leaks),
        leak_profile=leak_profile,
        leak_commits=leak_commits,
        leak_files=leak_files,
        scanned_at=scanned_at,
    )


def main():
    parser = argparse.ArgumentParser(description="Generate SVG status card from scan summary")
    parser.add_argument("--summary", default="results/summary.json")
    parser.add_argument("--output", default="results/card.svg")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found. Run scan.py first.", file=sys.stderr)
        sys.exit(1)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    svg = generate(summary)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"Card written to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
