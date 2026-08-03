"""Run ANKA's source pulls for one exact reporting period."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "working" / "reports"
CONNECTORS = {
    "ga4": ROOT / "skills" / "pull-ga4-skill" / "pull_ga4.py",
    "meta": ROOT / "skills" / "pull-meta-skill" / "pull_meta.py",
    "mailerlite": ROOT / "skills" / "pull-mailerlite-skill" / "pull_mailerlite.py",
    "tiktok": ROOT / "skills" / "pull-tiktok-skill" / "pull_tiktok.py",
}
DEFAULT_SOURCES = ["ga4", "meta", "mailerlite"]
SNAPSHOT_BUILDER = ROOT / "build_dashboard_snapshot.py"
ACTION_AGENT = ROOT / "action_agent" / "run_agent.py"


def completed_week():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    end = monday - timedelta(days=1)
    start = end - timedelta(days=6)
    return start.isoformat(), end.isoformat()


def run_source(source, script, since, until):
    command = [
        sys.executable,
        str(script),
        "--since",
        since,
        "--until",
        until,
    ]
    if source in {"ga4", "meta"}:
        command.extend(["--weeks", "2"])
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "source": source,
        "status": "SUCCESS" if result.returncode == 0 else "FAILED",
        "return_code": result.returncode,
        "stdout_tail": result.stdout[-3000:],
        "stderr_tail": result.stderr[-3000:],
    }


def run_action_workflow():
    snapshot = subprocess.run(
        [sys.executable, str(SNAPSHOT_BUILDER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if snapshot.returncode != 0:
        return {
            "status": "FAILED",
            "stage": "snapshot",
            "stdout_tail": snapshot.stdout[-3000:],
            "stderr_tail": snapshot.stderr[-3000:],
        }
    meta_reports = sorted(REPORTS.glob("meta_raw_*.json"))
    command = [sys.executable, str(ACTION_AGENT)]
    if meta_reports:
        command.extend(["--meta-raw", str(meta_reports[-1])])
    agent = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if agent.returncode == 0:
        refreshed_snapshot = subprocess.run(
            [sys.executable, str(SNAPSHOT_BUILDER)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if refreshed_snapshot.returncode != 0:
            return {
                "status": "FAILED",
                "stage": "snapshot_refresh",
                "stdout_tail": refreshed_snapshot.stdout[-3000:],
                "stderr_tail": refreshed_snapshot.stderr[-3000:],
            }
    return {
        "status": "SUCCESS" if agent.returncode == 0 else "FAILED",
        "stage": "action_agent",
        "return_code": agent.returncode,
        "stdout_tail": agent.stdout[-3000:],
        "stderr_tail": agent.stderr[-3000:],
    }


def main():
    parser = argparse.ArgumentParser(description="Run ANKA weekly data connectors")
    parser.add_argument("--since", help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--until", help="Inclusive end date YYYY-MM-DD")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=sorted(CONNECTORS),
        default=DEFAULT_SOURCES,
        help="TikTok is opt-in until OAuth has been completed and validated.",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Pull sources only; do not build the evidence-to-action brief.",
    )
    args = parser.parse_args()
    if bool(args.since) != bool(args.until):
        parser.error("--since and --until must be provided together")
    since, until = (
        (args.since, args.until) if args.since else completed_week()
    )

    results = [
        run_source(source, CONNECTORS[source], since, until)
        for source in args.sources
    ]
    connectors_succeeded = all(row["status"] == "SUCCESS" for row in results)
    agent_run = (
        run_action_workflow()
        if connectors_succeeded and not args.skip_agent
        else {
            "status": "SKIPPED",
            "stage": "action_agent",
            "reason": (
                "explicitly skipped"
                if args.skip_agent
                else "one or more source connectors failed"
            ),
        }
    )
    pipeline_succeeded = connectors_succeeded and agent_run["status"] in {"SUCCESS", "SKIPPED"}
    REPORTS.mkdir(parents=True, exist_ok=True)
    manifest = {
        "period": {"since": since, "until": until},
        "results": results,
        "action_agent": agent_run,
        "all_succeeded": pipeline_succeeded,
        "note": "Connector success does not imply data-quality approval. Read each source's quality output.",
    }
    output = REPORTS / f"pipeline_manifest_{date.today().isoformat()}.json"
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    for row in results:
        print(f"{row['source']}: {row['status']}")
    print(f"action_agent: {agent_run['status']}")
    print(f"Manifest: {output.relative_to(ROOT)}")
    raise SystemExit(0 if pipeline_succeeded else 1)


if __name__ == "__main__":
    main()
