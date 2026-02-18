"""Eval orchestrator — load cases, invoke claude -p, run validators, write JSON results."""

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

import yaml

from validators import run_all

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = Path(__file__).resolve().parent / "cases"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Directories to symlink read-only into the working directory
READONLY_LINKS = ["schemas", "lib", "skills", ".claude"]


def load_cases(
    tags: list[str] | None = None,
    case_id: str | None = None,
) -> list[dict]:
    """Load and filter case YAML files."""
    cases = []
    for case_file in sorted(CASES_DIR.rglob("*.yaml")):
        with open(case_file) as f:
            case = yaml.safe_load(f)
        if case is None:
            continue
        case["_file"] = str(case_file)
        cases.append(case)

    if case_id:
        cases = [c for c in cases if c.get("id") == case_id]
    elif tags:
        cases = [c for c in cases if set(tags) & set(c.get("tags", []))]

    return cases


def setup_workdir(tmp_base: Path) -> Path:
    """Create a working directory that mirrors the repo layout."""
    work_dir = tmp_base / "repo"
    work_dir.mkdir()

    # Symlink read-only directories
    for name in READONLY_LINKS:
        src = REPO_ROOT / name
        if src.exists():
            (work_dir / name).symlink_to(src)

    # Create writable examples directory
    (work_dir / "examples").mkdir()

    # Copy the CLAUDE.md so the skill can read project instructions
    claude_md = REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        shutil.copy2(claude_md, work_dir / "CLAUDE.md")

    return work_dir


def find_app_dir(work_dir: Path) -> Path | None:
    """Find the generated app directory under examples/."""
    examples = work_dir / "examples"
    if not examples.exists():
        return None

    # Look for directories with manifest.json
    for candidate in examples.iterdir():
        if candidate.is_dir() and (candidate / "manifest.json").exists():
            return candidate

    return None


def run_claude(prompt: str, work_dir: Path, budget: float, timeout: int) -> dict:
    """Invoke claude -p in headless mode and return structured result."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--permission-mode",
        "acceptEdits",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--max-budget-usd",
        str(budget),
    ]

    env = os.environ.copy()
    # Allow launching claude from within a Claude Code session
    env.pop("CLAUDECODE", None)

    try:
        result = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        # Try to parse JSON output
        try:
            output = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            output = {"raw_stdout": result.stdout[:2000]}

        return {
            "exit_code": result.returncode,
            "output": output,
            "stderr": result.stderr[:2000] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "output": {},
            "stderr": f"Timed out after {timeout}s",
        }
    except FileNotFoundError:
        return {
            "exit_code": -1,
            "output": {},
            "stderr": "claude CLI not found on PATH",
        }


def run_case(case: dict, run_dir: Path) -> dict:
    """Execute a single eval case end-to-end."""
    case_id = case.get("id", "unknown")
    prompt = case.get("prompt", "")
    budget = case.get("budget_usd", 2.0)
    timeout = case.get("timeout_sec", 300)

    print(f"\n{'=' * 60}")
    print(f"  Case: {case_id}")
    print(f"  Prompt: {prompt}")
    print(f"  Budget: ${budget:.2f} | Timeout: {timeout}s")
    print(f"{'=' * 60}")

    with tempfile.TemporaryDirectory(prefix=f"eval-{case_id}-") as tmp_str:
        tmp = Path(tmp_str)
        work_dir = setup_workdir(tmp)

        # Invoke claude
        print("  Invoking claude -p ...")
        claude_result = run_claude(prompt, work_dir, budget, timeout)

        if claude_result["exit_code"] != 0 and not claude_result["output"]:
            print(f"  Claude failed (exit {claude_result['exit_code']})")
            if claude_result["stderr"]:
                print(f"  stderr: {claude_result['stderr'][:200]}")

        # Find the generated app
        app_dir = find_app_dir(work_dir)

        if app_dir is None:
            print("  No app directory found!")
            result = {
                "case_id": case_id,
                "passed": False,
                "claude_result": claude_result,
                "validation": {
                    "passed": False,
                    "error_count": 1,
                    "warning_count": 0,
                    "findings": [
                        {
                            "rule": "SETUP",
                            "severity": "error",
                            "message": "No generated app found (no examples/*/manifest.json)",
                            "file": None,
                        }
                    ],
                    "errors": [],
                },
            }
        else:
            app_name = app_dir.name
            print(f"  Found app: examples/{app_name}/")

            # Run validators
            print("  Running validators ...")
            validation = run_all(app_dir, case)

            # Copy app for inspection
            case_result_dir = run_dir / case_id
            case_result_dir.mkdir(parents=True, exist_ok=True)
            app_dest = case_result_dir / "app"
            if app_dest.exists():
                shutil.rmtree(app_dest)
            shutil.copytree(app_dir, app_dest)

            result = {
                "case_id": case_id,
                "passed": validation.passed,
                "app_name": app_name,
                "claude_result": claude_result,
                "validation": validation.to_dict(),
            }

        # Print summary
        vr = result["validation"]
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  Result: {status} ({vr['error_count']} errors, {vr['warning_count']} warnings)")

        for f in vr.get("findings", []):
            if f["severity"] == "error":
                print(f"    ERROR [{f['rule']}] {f['message']}")
        for e in vr.get("errors", []):
            lines = e.splitlines()
            print(f"    CRASH: {lines[0]}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Upjack app-builder skill evaluator")
    parser.add_argument("--tags", nargs="*", help="Filter cases by tag")
    parser.add_argument("--case", help="Run a single case by ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="List matching cases without running"
    )
    args = parser.parse_args()

    cases = load_cases(tags=args.tags, case_id=args.case)

    if not cases:
        print("No matching cases found.")
        sys.exit(1)

    if args.dry_run:
        print(f"Found {len(cases)} matching case(s):\n")
        for c in cases:
            tags = ", ".join(c.get("tags", []))
            print(f"  {c['id']:30s} [{tags}]  {c.get('description', '')}")
        sys.exit(0)

    # Create run directory
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Eval run: {timestamp}")
    print(f"Cases: {len(cases)}")
    print(f"Results: {run_dir}")

    results = []
    for case in cases:
        result = run_case(case, run_dir)
        results.append(result)

    # Write summary
    summary = {
        "timestamp": timestamp,
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "cases": results,
    }

    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))

    # Final report
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {summary['passed']}/{summary['total']} passed")
    print(f"  Results: {summary_path}")
    print(f"{'=' * 60}")

    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
