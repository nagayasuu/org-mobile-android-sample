#!/usr/bin/env python3
"""Read the Android CI run for an explicit PR number or main commit."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ci_verification import SHA
from integrate_pr import APK_ARTIFACT, REPO, check_run_ids, github_api, require, run_matches


WORKFLOW = "actions/workflows/android.yml"


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def pr_target(repo, number):
    pr = github_api(repo, f"pulls/{number}")
    head, base = pr["head"], pr["base"]
    require(pr["number"] == number and base["ref"] == "main"
            and base["repo"]["full_name"].lower() == repo.lower()
            and head["repo"] and head["repo"]["full_name"].lower() == repo.lower()
            and SHA.fullmatch(head["sha"]), "Expected a same-repository PR targeting main")
    return head["sha"], head["ref"], pr["created_at"]


def required_checks(repo, number):
    result = subprocess.run(["gh", "pr", "checks", str(number), "--repo", f"github.com/{repo}",
                             "--required", "--json", "name,bucket,link"],
                            capture_output=True, text=True, timeout=90)
    if (result.returncode == 1 and not result.stdout.strip()
            and result.stderr.startswith(("no checks reported on the ", "no required checks reported on the "))):
        return []
    require(result.returncode in (0, 1, 8), "Cannot read required checks")
    checks = json.loads(result.stdout)
    require(isinstance(checks, list), "Invalid required checks response")
    return [check for check in checks if check["name"] == "verify"]


def artifact_status(artifacts, started, name):
    if not started:
        return "unconfirmed"
    start = timestamp(started)
    matches = [item for item in artifacts if item["name"] == name
               and timestamp(item["created_at"]) >= start]
    if not matches:
        return "missing"
    if len(matches) != 1:
        return "ambiguous"
    return "expired" if matches[0]["expired"] else "available"


def run_items(repo, path, key):
    result = github_api(repo, f"{path}?per_page=100")
    require(result["total_count"] == len(result[key]), f"Incomplete {key} response")
    return result[key]


def lookup(repo, *, pr=None, sha=None, diagnose=False):
    expected_job, checks = None, []
    if pr is not None:
        target = pr_target(repo, pr)
        sha, branch, opened = target
        event = "pull_request"
        checks = required_checks(repo, pr)
        candidates = [check_run_ids(repo, check["link"]) for check in checks if check["link"]]
    else:
        branch, event = "main", "push"
        listing = github_api(repo, f"{WORKFLOW}/runs?branch=main&event=push&head_sha={sha}&per_page=2")
        require(len(listing["workflow_runs"]) == min(2, listing["total_count"]), "Incomplete run response")
        candidates = [(run["id"], None) for run in listing["workflow_runs"]]
    result = dict(repo=repo, pr=pr, sha=sha, event=event)
    if not candidates:
        return dict(result, status="not-found")
    if len(candidates) > 1 or len(checks) > 1:
        return dict(result, status="ambiguous", candidate_run_ids=sorted({run for run, _ in candidates}))
    run_id, expected_job = candidates[0]
    workflow = github_api(repo, WORKFLOW)["id"]
    path = f"actions/runs/{run_id}"
    run = github_api(repo, path)
    require(run["id"] == run_id and run_matches(run, repo, workflow, event, branch, sha),
            "CI run belongs to a different workflow, branch or SHA")
    attempt = run["run_attempt"]
    if pr is not None:
        associated = {item["number"] for item in run["pull_requests"]}
        if (associated and pr not in associated) or timestamp(run["created_at"]) < timestamp(opened):
            return dict(result, status="unconfirmed", reason="pr-association", run=run_id, attempt=attempt)
    jobs = run_items(repo, f"{path}/attempts/{attempt}/jobs", "jobs")
    verify = [job for job in jobs if job["name"] == "verify"]
    require(len(verify) <= 1, "Multiple verify jobs")
    if expected_job is not None and (not verify or verify[0]["id"] != expected_job):
        return dict(result, status="changed", run=run_id, attempt=attempt)
    job = verify[0] if verify else None
    artifacts = run_items(repo, f"{path}/artifacts", "artifacts") if job and job.get("started_at") else []
    if (github_api(repo, path)["run_attempt"] != attempt
            or (pr is not None and (pr_target(repo, pr) != target or required_checks(repo, pr) != checks))):
        return dict(result, status="changed", run=run_id, attempt=attempt)
    state = run["status"]
    if state != "completed":
        status = "pending"
    elif not job:
        status = "unconfirmed"
    elif (run["conclusion"] == job["conclusion"] == "success"
          and (not checks or checks[0]["bucket"] == "pass")):
        status = "success"
    else:
        status = "unsuccessful"
    result.update(status=status, run=run_id, attempt=attempt, run_status=state,
                  run_conclusion=run["conclusion"], verify_conclusion=job["conclusion"] if job else None,
                  url=f"https://github.com/{repo}/actions/runs/{run_id}",
                  apk=artifact_status(artifacts, job.get("started_at") if job else None, APK_ARTIFACT))
    if diagnose:
        failed = [step for step in job.get("steps", []) if step.get("conclusion") in
                  ("failure", "timed_out", "cancelled", "action_required", "startup_failure")] if job else []
        first = min(failed, key=lambda step: step["number"]) if failed else None
        result.update(verify_job=job["id"] if job else None,
                      first_failed_step={key: first[key] for key in ("number", "name", "conclusion")}
                      if first else None,
                      reports=artifact_status(artifacts, job.get("started_at") if job else None, "android-reports")
                      if pr is not None else "not-applicable")
    return result


def save_failure_log(result, destination):
    if result["status"] != "unsuccessful" or not result.get("verify_job"):
        return "not-applicable"
    # Keep partial output private and publish the complete file without replacing an existing one.
    with tempfile.NamedTemporaryFile(dir=destination.parent) as log:
        process = subprocess.run([
            "gh", "run", "view", str(result["run"]), "--repo", f"github.com/{result['repo']}",
            "--attempt", str(result["attempt"]), "--job", str(result["verify_job"]), "--log-failed",
        ], stdout=log, stderr=subprocess.DEVNULL, timeout=90)
        if process.returncode or not os.fstat(log.fileno()).st_size:
            return "unavailable"
        os.link(log.name, destination)
    return "saved"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int)
    target.add_argument("--main-sha")
    parser.add_argument("--diagnose", action="store_true", help="Show the failed verify step and reports")
    parser.add_argument("--log-file", type=Path, help="Save failed-step logs to a new local file")
    args = parser.parse_args()
    if not REPO.fullmatch(args.repo) or args.repo.split("/")[1] in {".", ".."}:
        parser.error("Specify a GitHub owner/repo")
    if (args.pr is not None and args.pr <= 0) or (args.main_sha is not None and not SHA.fullmatch(args.main_sha)):
        parser.error("Specify a positive PR number or full main SHA")
    if args.log_file is not None and not args.diagnose:
        parser.error("--log-file requires --diagnose")
    try:
        result = lookup(args.repo, pr=args.pr, sha=args.main_sha, diagnose=args.diagnose)
    except (KeyError, OSError, TypeError, ValueError, subprocess.TimeoutExpired):
        print("CI lookup failed; check the target and GitHub CLI access", file=sys.stderr)
        return 2
    if args.log_file is not None:
        try:
            result["log"] = save_failure_log(result, args.log_file)
        except (OSError, subprocess.TimeoutExpired):
            result["log"] = "unavailable"
    print(json.dumps(result))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
