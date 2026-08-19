#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""SDK proto sync utilities.

Drift detection is handled by per-SDK mise tasks (go:proto:drift,
sdk:ts:proto:drift) which output JSON DriftReport objects. This CLI
provides the workflow integration layer: dashboards, issue management,
and wiki updates.

Subcommands:
  dashboard      Generate wiki dashboard markdown from drift/build reports
  wiki-push      Clone wiki repo, update a page, commit, push
  manage-issue   Create or update a GitHub drift issue (deduplicates by label)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SDK_CONFIGS = {
    "go": {
        "display_name": "Go",
        "source_dirs": [
            "sdk/go/openshell/v1/internal/converter/",
            "sdk/go/openshell/v1/types/",
            "sdk/go/openshell/v1/",
        ],
        "proto_task": "go:proto:gen",
        "build_task": "go:build",
        "test_task": "go:test",
    },
    "typescript": {
        "display_name": "TypeScript",
        "source_dirs": [
            "sdk/typescript/src/",
        ],
        "proto_task": "sdk:ts:proto",
        "build_task": "sdk:ts:build",
        "test_task": "sdk:ts:test",
    },
}


def _sdk_display_name(sdk: str) -> str:
    return SDK_CONFIGS[sdk]["display_name"]


def generate_dashboard(
    drift_reports: list[dict],
    build_reports: list[dict],
) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# SDK Sync Status",
        "",
        f"*Last updated: {timestamp}*",
        "",
        "## Overview",
        "",
        "| SDK | Proto Synced | Build | Issue |",
        "|-----|-------------|-------|-------|",
    ]

    drift_details: list[str] = []

    for drift in drift_reports:
        sdk = drift.get("sdk", "unknown")
        synced = drift.get("synced", True)
        build = _find_build(build_reports, sdk)

        if synced:
            proto_status = "synced"
            build_status = "n/a"
            issue_link = ""
        else:
            proto_status = "**drifted**"
            if build and not build.get("success", True):
                build_status = "**failing**"
            else:
                build_status = "passing"
            issue_link = drift.get("issue_url", "")
            if issue_link:
                issue_num = issue_link.rstrip("/").split("/")[-1]
                issue_link = f"[#{issue_num}]({issue_link})"

        lines.append(
            f"| {_sdk_display_name(sdk)} | {proto_status} | {build_status} | {issue_link} |"
        )

        if not synced:
            drift_details.extend(_format_drift_details(drift))

    if drift_details:
        lines.append("")
        lines.append("## Drift Details")
        lines.append("")
        lines.extend(drift_details)

    lines.append("")
    return "\n".join(lines)


def generate_issue_body(
    drift_report: dict,
    build_report: dict | None,
    sdk: str,
    max_log_lines: int = 500,
) -> str:
    sections: list[str] = []
    paths = SDK_CONFIGS[sdk]

    sections.append("## Proto Drift Report")
    sections.append("")
    summary = drift_report.get("summary", "unknown")
    sections.append(f"**Summary**: {summary}")
    sections.append("")

    files = drift_report.get("files", [])
    drifted_files = [f for f in files if f.get("status") != "synced"]

    if drifted_files:
        sections.extend(_render_file_table(drifted_files))
    sections.append("")

    if build_report:
        sections.append("## Build Log")
        sections.append("")
        failed_step = build_report.get("failed_step", "unknown")
        sections.append(f"**Failed step**: `{failed_step}`")
        sections.append("")
        log = build_report.get("log", "no log available")
        log_lines = log.splitlines()
        if len(log_lines) > max_log_lines:
            log = "\n".join(log_lines[-max_log_lines:])
        sections.append("```")
        sections.append(log)
        sections.append("```")
        sections.append("")

    sections.append("## Fix Commands")
    sections.append("")
    sections.append("```bash")
    sections.append(f"mise run {paths['proto_task']}    # Regenerate bindings")
    sections.append(f"mise run {paths['build_task']}    # Verify build")
    sections.append(f"mise run {paths['test_task']}     # Run tests")
    sections.append("```")
    sections.append("")

    drifted_names = ", ".join(f"`{f['name']}`" for f in drifted_files) or "unknown"
    failed_step = ""
    if build_report:
        failed_step = build_report.get("failed_step", "")

    sections.append("## Agent Instructions")
    sections.append("")
    sections.append(
        "This section is a ready-to-consume prompt for an AI agent. "
        "Copy it into your agent to produce a fix PR."
    )
    sections.append("")
    sections.append("<details>")
    sections.append("<summary>Agent prompt (click to expand)</summary>")
    sections.append("")

    display_name = _sdk_display_name(sdk)
    sections.append(f"Fix proto drift in the {display_name} SDK.")
    sections.append("")
    sections.append("## Context")
    sections.append("")
    sections.append(
        f"The root `proto/` directory has changed and the {display_name} SDK's"
    )
    sections.append(
        f"generated bindings are out of sync. The drifted files are: {drifted_names}."
    )

    if failed_step:
        sections.append(
            f"The SDK build fails at the `{failed_step}` step after regenerating protos."
        )
        sections.append(
            "The build log above shows the exact error. Your job is to fix the"
        )
        sections.append(
            f"{display_name} SDK code so it compiles and passes tests with the updated protos."
        )
    else:
        sections.append(
            "The SDK build status is unknown. Check if it compiles after regeneration."
        )

    sections.append("")
    sections.append("## Steps")
    sections.append("")
    sections.append(
        f"1. **Regenerate bindings**: Run `mise run {paths['proto_task']}` to regenerate "
        "language-specific bindings from the updated protos."
    )
    sections.append(
        "2. **Fix compilation errors**: Read the build log above. Update the SDK source code "
        "to handle new/changed/removed proto fields:"
    )
    for source_dir in paths["source_dirs"]:
        sections.append(f"   - `{source_dir}`")
    sections.append(
        "3. **Fix test failures**: Update tests that assert on proto types that changed shape."
    )
    sections.append(
        f"4. **Verify**: Run `mise run {paths['build_task']}` and "
        f"`mise run {paths['test_task']}` until both pass."
    )
    sections.append(
        "5. **Create a PR**: Commit all changes and create a PR referencing this issue."
    )
    sections.append("")
    sections.append("## Scope")
    sections.append("")
    sections.append(
        f"- Only modify files under `sdk/{sdk}/`. Do not change root `proto/` files."
    )
    sections.append(
        "- Do not change the proto definitions. Adapt the SDK to match them."
    )
    sections.append("- Keep changes minimal: only fix what the proto changes broke.")

    sections.append("")
    sections.append("</details>")
    sections.append("")

    return "\n".join(sections)


# --- helpers ---


def _find_build(build_reports: list[dict], sdk: str) -> dict | None:
    return next((b for b in build_reports if b.get("sdk") == sdk), None)


def _render_file_table(files: list[dict]) -> list[str]:
    lines = [
        "| File | Status | Diff Lines |",
        "|------|--------|------------|",
    ]
    for f in files:
        lines.append(f"| `{f['name']}` | {f['status']} | {f['diff_lines']} |")
    return lines


def _format_drift_details(drift: dict) -> list[str]:
    sdk = drift.get("sdk", "unknown")
    lines = [
        f"### {_sdk_display_name(sdk)} SDK",
        "",
        f"**Status**: {drift.get('summary', 'unknown')}",
        "",
    ]
    files = drift.get("files", [])
    if files:
        lines.extend(_render_file_table(files))
        lines.append("")
    return lines


def _run_cmd(
    cmd: list[str], cwd: str | None = None, capture: bool = False
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
    )


def _ensure_label(repo: str, label: str, description: str) -> None:
    check = _run_cmd(["gh", "label", "view", label, "--repo", repo], capture=True)
    if check.returncode != 0:
        _run_cmd(
            [
                "gh",
                "label",
                "create",
                label,
                "--repo",
                repo,
                "--description",
                description,
                "--color",
                "D93F0B",
            ],
            capture=True,
        )


def _find_open_issue(repo: str, label: str) -> dict | None:
    result = _run_cmd(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            label,
            "--state",
            "open",
            "--json",
            "url,number",
            "--jq",
            ".[0]",
        ],
        capture=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            data = json.loads(result.stdout.strip())
            return {"url": data["url"], "number": str(data["number"])}
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return None


# --- public functions ---


def wiki_push(content_path: Path, page_name: str, repo: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"success": False, "reason": "GITHUB_TOKEN not set"}

    work_dir = tempfile.mkdtemp()
    try:
        clone_url = f"https://x-access-token:{token}@github.com/{repo}.wiki.git"
        result = _run_cmd(["git", "clone", clone_url, work_dir], capture=True)
        if result.returncode != 0:
            return {
                "success": False,
                "reason": "Failed to clone wiki repository",
            }

        shutil.copy2(str(content_path), str(Path(work_dir) / f"{page_name}.md"))

        _run_cmd(["git", "config", "user.name", "github-actions[bot]"], cwd=work_dir)
        _run_cmd(
            [
                "git",
                "config",
                "user.email",
                "github-actions[bot]@users.noreply.github.com",
            ],
            cwd=work_dir,
        )
        _run_cmd(["git", "add", f"{page_name}.md"], cwd=work_dir)

        diff = _run_cmd(
            ["git", "diff", "--cached", "--quiet"], cwd=work_dir, capture=True
        )
        if diff.returncode == 0:
            return {"success": True, "reason": "No changes to dashboard"}

        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        _run_cmd(
            ["git", "commit", "-m", f"Update {page_name} ({timestamp})"],
            cwd=work_dir,
        )

        push = _run_cmd(["git", "push"], cwd=work_dir, capture=True)
        if push.returncode != 0:
            return {"success": False, "reason": "Failed to push wiki update"}

        return {"success": True, "reason": "Wiki updated"}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def manage_issue(
    drift_report: dict,
    build_report: dict | None,
    sdk: str,
    repo: str,
    label: str,
) -> dict:
    _ensure_label(repo, label, f"Proto drift detected for {sdk} SDK")

    body = generate_issue_body(drift_report, build_report, sdk)
    title = f"SDK proto drift: {sdk}"

    existing = _find_open_issue(repo, label)
    if existing:
        result = _run_cmd(
            [
                "gh",
                "issue",
                "edit",
                existing["number"],
                "--repo",
                repo,
                "--body",
                body,
            ],
            capture=True,
        )
        if result.returncode == 0:
            return {"issue_url": existing["url"], "action": "updated"}
        return {
            "issue_url": "",
            "action": "error",
            "reason": "Failed to update issue",
        }

    result = _run_cmd(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            body,
            "--label",
            label,
        ],
        capture=True,
    )
    if result.returncode == 0:
        url = result.stdout.strip()
        return {"issue_url": url, "action": "created"}
    return {
        "issue_url": "",
        "action": "error",
        "reason": "Failed to create issue",
    }


# --- CLI ---


def _load_json_arg(value: str) -> dict | list:
    if value == "-":
        return json.load(sys.stdin)
    return json.loads(value)


def cmd_dashboard(args: argparse.Namespace) -> int:
    drift_reports = _load_json_arg(args.drift_report)
    if not isinstance(drift_reports, list):
        drift_reports = [drift_reports]

    build_reports: list[dict] = []
    if args.build_report:
        br = _load_json_arg(args.build_report)
        build_reports = br if isinstance(br, list) else [br]

    md = generate_dashboard(drift_reports, build_reports)

    if args.output:
        Path(args.output).write_text(md)
        print(f"Dashboard written to {args.output}")
    else:
        print(md)
    return 0


def cmd_wiki_push(args: argparse.Namespace) -> int:
    content = Path(args.content)
    if not content.exists():
        print(f"ERROR: Content file not found: {content}", file=sys.stderr)
        return 1
    result = wiki_push(content, args.page_name, args.repo)
    print(json.dumps(result))
    return 0


def cmd_manage_issue(args: argparse.Namespace) -> int:
    drift_report = _load_json_arg(args.drift_report)
    build_report = None
    if args.build_report:
        build_report = _load_json_arg(args.build_report)
    result = manage_issue(drift_report, build_report, args.sdk, args.repo, args.label)
    print(json.dumps(result))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SDK proto sync utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    db = sub.add_parser("dashboard", help="Generate wiki dashboard markdown")
    db.add_argument(
        "--drift-report",
        required=True,
        help="Drift report JSON (string or - for stdin)",
    )
    db.add_argument("--build-report", help="Build report JSON (string or - for stdin)")
    db.add_argument("--output", help="Output file path (stdout if omitted)")

    wp = sub.add_parser("wiki-push", help="Push a page to the GitHub wiki")
    wp.add_argument("--content", required=True, help="Path to markdown file to push")
    wp.add_argument("--page-name", required=True, help="Wiki page name (without .md)")
    wp.add_argument("--repo", required=True, help="GitHub repo (owner/name)")

    mi = sub.add_parser("manage-issue", help="Create or update a drift issue")
    mi.add_argument("--drift-report", required=True, help="Drift report JSON")
    mi.add_argument("--build-report", help="Build report JSON")
    mi.add_argument("--sdk", required=True, help="SDK name")
    mi.add_argument("--repo", required=True, help="GitHub repo (owner/name)")
    mi.add_argument("--label", required=True, help="Issue label for deduplication")

    args = parser.parse_args()
    handlers = {
        "dashboard": cmd_dashboard,
        "wiki-push": cmd_wiki_push,
        "manage-issue": cmd_manage_issue,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
