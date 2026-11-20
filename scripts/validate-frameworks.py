#!/usr/bin/env python3
"""Validate the target frameworks declared in .NET project files.

Scans *.csproj, *.fsproj, *.vbproj and Directory.Build.props files for
<TargetFramework> / <TargetFrameworks> and flags frameworks that are out of
support. Support data for .NET / .NET Core comes from Microsoft's official
release metadata, so the check stays current without code changes.

Environment variables:
  FRAMEWORKS_MODE      error | warning | off   (default: error)
  FRAMEWORKS_IGNORE    comma/space/newline separated TFMs to skip (e.g. "net8.0, net48")
  RELEASES_INDEX_URL   override for the .NET release metadata URL
  GITHUB_OUTPUT, GITHUB_ENV, GITHUB_STEP_SUMMARY  provided by GitHub Actions
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request

RELEASES_INDEX_URL = os.environ.get(
    "RELEASES_INDEX_URL",
    "https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/releases-index.json",
)

PROJECT_SUFFIXES = (".csproj", ".fsproj", ".vbproj")
EXTRA_FILES = ("directory.build.props",)
SKIP_DIRS = {".git", "bin", "obj", "node_modules", ".vs", ".idea", "packages"}

# .NET Framework lifecycle (not in the release metadata). Versions not listed here
# are out of support. A date means support ends on that day; None means support
# follows the Windows OS lifecycle.
NET_FRAMEWORK_SUPPORT = {
    "net35": ("3.5 SP1", dt.date(2029, 1, 9)),
    "net462": ("4.6.2", dt.date(2027, 1, 12)),
    "net47": ("4.7", None),
    "net471": ("4.7.1", None),
    "net472": ("4.7.2", None),
    "net48": ("4.8", None),
    "net481": ("4.8.1", None),
}

TFM_TAG = re.compile(
    r"<(TargetFrameworks?)\b[^>]*>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL
)
MODERN = re.compile(r"^net(?:coreapp)?(\d+)\.(\d+)(?:-[a-z0-9.]+)?$")
NETSTANDARD = re.compile(r"^netstandard\d+(\.\d+)?$")
NETFX = re.compile(r"^net\d{2,3}$")


def load_release_index() -> dict[str, dict] | None:
    try:
        with urllib.request.urlopen(RELEASES_INDEX_URL, timeout=15) as response:
            data = json.load(response)
        return {r["channel-version"]: r for r in data.get("releases-index", [])}
    except Exception as exc:  # noqa: BLE001 - any failure just disables the online check
        print(f"::warning::Could not download .NET release metadata ({exc}); "
              "support status of .NET / .NET Core frameworks cannot be verified.")
        return None


def find_project_files(root: str) -> list[str]:
    found = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS)
        for name in sorted(files):
            lower = name.lower()
            if lower.endswith(PROJECT_SUFFIXES) or lower in EXTRA_FILES:
                found.append(os.path.relpath(os.path.join(current, name), root))
    return found


def extract_frameworks(path: str) -> list[tuple[str, int]]:
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        text = handle.read()
    results = []
    for match in TFM_TAG.finditer(text):
        line = text.count("\n", 0, match.start(2)) + 1
        for tfm in match.group(2).split(";"):
            tfm = tfm.strip()
            if tfm:
                results.append((tfm, line))
    return results


def classify(tfm: str, releases: dict | None, today: dt.date) -> tuple[str, str]:
    """Return (status, message). status is ok | unsupported | unknown."""
    value = tfm.lower()

    if "$(" in value:
        return "unknown", f"`{tfm}` uses an MSBuild property and cannot be checked statically"

    if NETSTANDARD.match(value):
        return "ok", ".NET Standard (supported by every current .NET implementation)"

    modern = MODERN.match(value)
    if modern:
        channel = f"{modern.group(1)}.{modern.group(2)}"
        name = (".NET Core " if value.startswith("netcoreapp") or int(modern.group(1)) < 5 else ".NET ") + channel
        if releases is None:
            return "unknown", f"{name}: release metadata unavailable"
        release = releases.get(channel)
        if release is None:
            return "unknown", f"{name} is not a known .NET release"
        phase = release.get("support-phase", "")
        eol = release.get("eol-date")
        eol_date = dt.date.fromisoformat(eol) if eol else None
        if phase == "eol" or (eol_date and eol_date <= today):
            return "unsupported", f"{name} reached end of support on {eol or 'an earlier date'}"
        if phase == "preview":
            return "ok", f"{name} is a preview release"
        suffix = f", supported until {eol}" if eol else ""
        return "ok", f"{name} ({release.get('release-type', '').upper()}{suffix})"

    if NETFX.match(value):
        info = NET_FRAMEWORK_SUPPORT.get(value)
        if info is None:
            return "unsupported", f".NET Framework `{tfm}` is out of support (use 4.6.2 or later)"
        label, end = info
        if end and end <= today:
            return "unsupported", f".NET Framework {label} reached end of support on {end.isoformat()}"
        suffix = f", supported until {end.isoformat()}" if end else ""
        return "ok", f".NET Framework {label}{suffix}"

    return "unknown", f"`{tfm}` is not a recognised target framework moniker"


def write_kv(env_name: str, values: dict[str, str]) -> None:
    target = os.environ.get(env_name)
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    mode = os.environ.get("FRAMEWORKS_MODE", "error").strip().lower()
    if mode == "off":
        print("Target framework validation is disabled.")
        write_kv("GITHUB_ENV", {"framework_issues_detected": "false"})
        return 0
    if mode not in ("error", "warning"):
        print(f"::error::Invalid frameworks-validation value '{mode}'. Use error, warning or off.")
        return 1

    ignored = {
        t.strip().lower()
        for t in re.split(r"[,\s;]+", os.environ.get("FRAMEWORKS_IGNORE", ""))
        if t.strip()
    }
    today = dt.date.today()
    root = os.getcwd()

    files = find_project_files(root)
    if not files:
        print("No .NET project files found; skipping target framework validation.")
        write_kv("GITHUB_ENV", {"framework_issues_detected": "false"})
        return 0

    releases = None
    rows: list[tuple[str, int, str, str, str]] = []  # file, line, tfm, status, message
    for path in files:
        for tfm, line in extract_frameworks(os.path.join(root, path)):
            if tfm.lower() in ignored:
                rows.append((path, line, tfm, "ignored", "ignored by configuration"))
                continue
            if releases is None and MODERN.match(tfm.lower()):
                releases = load_release_index() or {}
            status, message = classify(tfm, releases if releases else None, today)
            rows.append((path, line, tfm, status, message))

    if not rows:
        print("No <TargetFramework> or <TargetFrameworks> declarations found.")
        write_kv("GITHUB_ENV", {"framework_issues_detected": "false"})
        return 0

    unsupported = [r for r in rows if r[3] == "unsupported"]
    unknown = [r for r in rows if r[3] == "unknown"]
    level = "error" if mode == "error" else "warning"

    print("Detected target frameworks:")
    for path, line, tfm, status, message in rows:
        icon = {"ok": "✅", "unsupported": "❌", "unknown": "⚠️", "ignored": "⏭️"}[status]
        print(f"  {icon} {path}:{line}  {tfm}  — {message}")
        if status == "unsupported":
            print(f"::{level} file={path},line={line},title=Unsupported target framework::{message}. "
                  "Upgrade the project to a supported framework.")
        elif status == "unknown":
            print(f"::warning file={path},line={line},title=Unverified target framework::{message}")

    frameworks = sorted({r[2] for r in rows}, key=str.lower)
    issues = bool(unsupported) and mode == "error"

    summary = ["## 🧱 .NET target framework issues detected" if unsupported
               else "## 🧱 .NET target frameworks", ""]
    summary += ["| File | Line | Framework | Status |", "|:-----|:----:|:----------|:-------|"]
    for path, line, tfm, status, message in rows:
        icon = {"ok": "✅", "unsupported": "❌", "unknown": "⚠️", "ignored": "⏭️"}[status]
        summary.append(f"| {path} | {line} | `{tfm}` | {icon} {message} |")
    if unsupported:
        summary += ["", "⚡ Please upgrade the projects above to a supported framework. "
                    "See the [.NET support policy](https://dotnet.microsoft.com/platform/support/policy)."]
    summary.append("")

    with open("frameworks-summary.md", "w", encoding="utf-8") as handle:
        handle.write("\n".join(summary))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(summary) + "\n")

    write_kv("GITHUB_OUTPUT", {
        "frameworks": ",".join(frameworks),
        "unsupported-frameworks": ",".join(sorted({r[2] for r in unsupported}, key=str.lower)),
    })
    write_kv("GITHUB_ENV", {"framework_issues_detected": "true" if issues else "false"})

    if unsupported:
        print(f"Found {len(unsupported)} unsupported target framework declaration(s).")
    if unknown:
        print(f"Found {len(unknown)} target framework declaration(s) that could not be verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
