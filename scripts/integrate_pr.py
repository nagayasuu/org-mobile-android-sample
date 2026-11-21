#!/usr/bin/env python3
"""Run PR integration steps and keep their evidence locally."""

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

from check_commit_message import validate
from ci_verification import APK, MANIFEST, SCHEMA_VERSION, SHA, apk_sha256, validate_results

STEPS = ("prepare", "create", "wait", "artifacts", "merge", "main-ci", "cleanup")
WRITES = {"create", "merge", "cleanup"}
VERIFICATION_ARTIFACT = "android-verification"
APK_ARTIFACT = "org-reader-debug"
ARTIFACTS = (VERIFICATION_ARTIFACT, APK_ARTIFACT, "android-reports")
REPO = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+")
BRANCH = re.compile(r"(feat|fix|docs|refactor|test|build|ci|chore)/[a-z0-9]+(?:-[a-z0-9]+)*")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(*args, timeout=90, stdin=None):
    result = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # CLI stderr may contain local paths or credential configuration.
        raise ValueError(f"{args[0]} {args[1]} failed (exit {result.returncode})")
    return result.stdout.strip()


def github_api(repo, path, *options, payload=None):
    return json.loads(command("gh", "api", "--hostname", "github.com",
                              f"repos/{repo}/{path}", *options,
                              stdin=json.dumps(payload) if payload is not None else None))


def check_run_ids(repo, url):
    match = re.fullmatch(rf"https://github\.com/{re.escape(repo)}/actions/runs/([1-9][0-9]*)(?:/job/([1-9][0-9]*))?",
                         url, re.I)
    require(match, "Unexpected verify check URL")
    return int(match[1]), int(match[2]) if match[2] else None


def run_matches(data, repo, workflow, event, branch, sha):
    return (data["workflow_id"] == workflow and data["event"] == event
            and data["head_branch"] == branch and data["head_sha"] == sha
            and data["head_repository"]["full_name"].lower() == repo.lower())


def timing_path(path):
    return path.with_suffix(path.suffix + ".timing.json")


def save_json(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(value, file, indent=2, allow_nan=False)
            file.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class Integration:
    def __init__(self, path, args):
        self.path = path
        self.args = args
        self.state = json.loads(path.read_text()) if path.exists() else {}
        require(isinstance(self.state, dict), "Journal must be a JSON object")
        repo = self.state.get("repo", args.repo)
        require(isinstance(repo, str) and REPO.fullmatch(repo) and repo.split("/")[1] not in {".", ".."},
                "Specify a GitHub owner/repo")
        if self.state:
            require(not args.repo or args.repo.lower() == repo.lower(), "--repo differs from journal")
            require(not args.head or args.head == self.state["head"], "--head differs from journal")
        self.repo = repo
        self.qualified_repo = f"github.com/{repo}"

    def api(self, path, *options, payload=None):
        return github_api(self.repo, path, *options, payload=payload)

    def save(self):
        save_json(self.path, self.state)

    def start_timing(self, step):
        if not getattr(self.args, "record_timing", False):
            return None
        path = timing_path(self.path)
        head = self.state.get("head", self.args.head)
        require(head and SHA.fullmatch(head), "Specify the full reviewed --head SHA")
        identity = dict(repo=self.repo.lower(), head=head)
        timing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(identity, attempts=[])
        require(isinstance(timing, dict) and all(timing.get(key) == value for key, value in identity.items())
                and isinstance(timing.get("attempts"), list), "Timing records differ from the current repo or SHA")
        timing["attempts"].append(dict(step=step, invoked_step=self.args.step, status="unfinished",
                                       started_utc=datetime.now(timezone.utc).isoformat(),
                                       ended_utc=None, elapsed_seconds=None))
        save_json(path, timing)
        return timing

    def branch_sha(self, branch):
        return self.api(f"branches/{quote(branch, safe='')}")["commit"]["sha"]

    def protection(self):
        p = self.api("branches/main/protection")
        checks = p["required_status_checks"]
        reviews = p["required_pull_request_reviews"]
        require(checks["strict"] and {"context": "verify", "app_id": 15368} in checks["checks"]
                and p["enforce_admins"]["enabled"] and p["required_conversation_resolution"]["enabled"]
                and not p["allow_force_pushes"]["enabled"] and not p["allow_deletions"]["enabled"]
                and reviews.get("bypass_pull_request_allowances", {}) in
                ({}, {"users": [], "teams": [], "apps": []}),
                "main protection differs from the documented policy")

    def live_refs(self):
        require(self.branch_sha(self.state["branch"]) == self.state["head"], "Remote head changed")
        require(self.branch_sha("main") == self.state["base"], "main changed since preparation")

    def prepare(self):
        require(self.args.head and SHA.fullmatch(self.args.head), "Specify the full reviewed --head SHA")
        branch = command("git", "branch", "--show-current")
        require(BRANCH.fullmatch(branch), "Use a work branch matching the repository convention")
        require(command("git", "rev-parse", "HEAD") == self.args.head, "Local head differs from reviewed SHA")
        require(not command("git", "status", "--porcelain"), "Worktree must be clean")
        base = self.branch_sha("main")
        require(base != self.args.head, "Work branch must differ from main")
        command("git", "merge-base", "--is-ancestor", base, self.args.head)
        require(self.branch_sha(branch) == self.args.head, "Push the reviewed head before preparing")
        self.protection()
        self.state.update(repo=self.repo, branch=branch, head=self.args.head, base=base,
                          workflow=self.api("actions/workflows/android.yml")["id"], done={})

    def check_pr(self, pr):
        s = self.state
        require(pr["head"]["sha"] == s["head"] and pr["head"]["ref"] == s["branch"]
                and (pr["head"]["repo"] or {}).get("full_name", "").lower() == self.repo.lower()
                and pr["base"]["ref"] == "main"
                and pr["base"]["repo"]["full_name"].lower() == self.repo.lower(),
                "PR head or repository changed")
        return pr

    def pr(self):
        return self.check_pr(self.api(f"pulls/{self.state['pr']}"))

    def create(self):
        self.live_refs()
        s = self.state
        owner = self.repo.split("/")[0]
        candidates = self.api("pulls", "--method", "GET", "-f", "state=open",
                              "-f", "base=main", "-f", f"head={owner}:{s['branch']}")
        require(len(candidates) <= 1, "Multiple open PRs match this branch")
        if candidates:
            pr = self.check_pr(candidates[0])
        else:
            require(not s.get("create_pending"), "Previous PR creation is unresolved; inspect GitHub before starting a new journal")
            require(self.args.title and self.args.body_file, "Specify --title and --body-file")
            title = self.args.title
            require("\n" not in title and "\r" not in title and not validate(title), "Invalid PR title")
            body = self.args.body_file.read_text()
            require(body.strip(), "PR body is empty")
            s["create_pending"] = True
            self.save()
            pr = self.check_pr(self.api("pulls", "--method", "POST", "--input", "-",
                                        payload=dict(base="main", head=s["branch"], title=title, body=body)))
        s["pr"] = pr["number"]
        s.pop("create_pending", None)

    def required_run(self):
        checks = json.loads(command("gh", "pr", "checks", str(self.state["pr"]),
                                    "--repo", self.qualified_repo, "--required", "--json", "name,bucket,link"))
        require(checks and all(c["bucket"] == "pass" for c in checks), "Required PR checks are incomplete")
        verify = [c for c in checks if c["name"] == "verify"]
        require(len(verify) == 1, "Expected one required verify check")
        return check_run_ids(self.repo, verify[0]["link"])

    def run(self, run_id, main=False):
        data = self.api(f"actions/runs/{run_id}")
        s = self.state
        require(data["id"] == run_id and run_matches(
                    data, self.repo, s["workflow"], "push" if main else "pull_request",
                    "main" if main else s["branch"], s["merged"] if main else s["head"]),
                "CI run belongs to a different workflow, branch or SHA")
        return data

    def success(self, run_id, main=False):
        data = self.run(run_id, main)
        require(data["status"] == "completed" and data["conclusion"] == "success", "CI has not succeeded")
        attempt = data["run_attempt"]
        jobs = self.api(f"actions/runs/{run_id}/attempts/{attempt}/jobs")["jobs"]
        verify = [job for job in jobs if job["name"] == "verify"]
        require(len(verify) == 1 and verify[0]["conclusion"] == "success", "verify has not succeeded")
        if not main:
            required_run, required_job = self.required_run()
            require(required_run == run_id and (required_job is None or required_job == verify[0]["id"]),
                    "Required check points to a different run or attempt")
        return attempt, verify[0]["started_at"]

    def watch(self, main=False):
        require(self.args.run and self.args.run > 0, "Specify the target --run ID")
        run_id = self.args.run
        self.run(run_id, main)
        command("gh", "run", "watch", str(run_id), "--repo", self.qualified_repo,
                "--compact", "--exit-status", "--interval", "5", timeout=self.args.timeout)
        return run_id, self.success(run_id, main)[0]

    def wait(self):
        self.live_refs()
        require(self.pr()["state"] == "open", "PR must be open")
        run, attempt = self.watch()
        self.live_refs()
        self.pr()
        self.state.update(run=run, attempt=attempt)

    def current_evidence(self):
        s = self.state
        attempt, started = self.success(s["run"])
        require(attempt == s["attempt"], "CI attempt changed")
        return started

    def artifact_ids(self, started):
        run = self.state["run"]
        data = self.api(f"actions/runs/{run}/artifacts")
        require(data["total_count"] == len(data["artifacts"]), "Artifact list is incomplete")
        ids = {}
        for name in ARTIFACTS:
            matches = [a for a in data["artifacts"] if a["name"] == name and not a["expired"]]
            require(len(matches) == 1, f"Expected one active {name} artifact")
            artifact = matches[0]
            require(datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00"))
                    >= datetime.fromisoformat(started.replace("Z", "+00:00")),
                    f"{name} artifact predates the verify job")
            ids[name] = artifact["id"]
        return ids

    def artifacts(self):
        self.live_refs()
        self.pr()
        started = self.current_evidence()
        ids = self.artifact_ids(started)
        s = self.state
        with tempfile.TemporaryDirectory(dir=self.path.parent) as directory:
            for name in (VERIFICATION_ARTIFACT, APK_ARTIFACT):
                command("gh", "run", "download", str(s["run"]), "--repo", self.qualified_repo,
                        "--name", name, "--dir", str(Path(directory) / name))
            root = Path(directory)
            path = root / VERIFICATION_ARTIFACT / MANIFEST
            require(path.is_file(), "Missing CI verification manifest")
            report = json.loads(path.read_text(encoding="utf-8"))
            require(isinstance(report, dict) and type(report.get("schema_version")) is int
                    and report["schema_version"] == SCHEMA_VERSION, "Unsupported CI verification schema")
            repo = report.get("repository")
            require(isinstance(repo, str) and repo.lower() == self.repo.lower()
                    and report.get("event") == "pull_request",
                    "CI verification manifest belongs to a different repository or event")
            for field, expected in (("run_id", s["run"]), ("run_attempt", s["attempt"]), ("pr_number", s["pr"])):
                require(type(report.get(field)) is int and report[field] == expected,
                        f"CI verification manifest differs in {field}")
            require(report.get("pr_head_sha") == s["head"], "CI verification manifest has a different PR head")
            tested = report.get("tested_sha")
            require(isinstance(tested, str) and SHA.fullmatch(tested) and tested != s["head"],
                    "Expected the tested PR merge SHA")
            parents = [s["base"], s["head"]]
            require(report.get("parents") == parents, "CI verification manifest has unexpected parents")
            with redirect_stdout(sys.stderr):
                validate_results(report)
            coverage = report["coverage"]
            require(coverage.get("base") == s["base"], "CI coverage base differs")
            commit = self.api(f"git/commits/{tested}")
            require([p["sha"] for p in commit["parents"]] == parents, "CI merge commit has unexpected parents")
            require(commit["tree"]["sha"] == command("git", "rev-parse", f"{s['head']}^{{tree}}"),
                    "CI tested different content")
            apk = root / APK_ARTIFACT / APK.name
            require(apk.is_file(), "Missing debug APK")
            require(apk_sha256(apk) == report["apk_sha256"], "Debug APK SHA-256 differs from CI")
            require(self.artifact_ids(self.current_evidence()) == ids, "Artifacts changed during download")
            self.live_refs()
            s["evidence"] = dict(schema_version=SCHEMA_VERSION, tested_sha=tested, parents=parents,
                                 apk_sha256=report["apk_sha256"], tests=report["tests"], lint=report["lint"],
                                 coverage=coverage["counters"], regression=coverage["regression"], artifacts=ids)

    def merge(self):
        s = self.state
        pr = self.pr()
        if not pr.get("merged"):
            require(not s.get("merge_pending"), "Previous merge is unresolved; inspect the PR before retrying")
            self.protection()
            started = self.current_evidence()
            evidence = s["evidence"]
            require(evidence.get("schema_version") == SCHEMA_VERSION,
                    "Journal lacks CI verification manifest evidence; prepare a new journal for a supported run")
            require(self.artifact_ids(started) == evidence["artifacts"],
                    "Artifacts changed since verification")
            require(self.args.title and self.args.body_file, "Specify the squash title and body")
            body = self.args.body_file.read_text()
            require(len(self.args.title.splitlines()) == 1 and "\r" not in self.args.title
                    and "\n" not in self.args.title and body.strip()
                    and not validate(self.args.title + "\n\n" + body), "Invalid squash commit message")
            self.live_refs()
            pr = self.pr()
            require(pr["state"] == "open" and not pr["draft"], "PR must be open and ready")
            s["merge_pending"] = True
            self.save()
            result = self.api(f"pulls/{s['pr']}/merge", "--method", "PUT", "--input", "-",
                              payload=dict(merge_method="squash", sha=s["head"],
                                           commit_title=self.args.title, commit_message=body))
            require(result["merged"], "GitHub rejected the squash merge")
            pr = self.pr()
        require(pr["merged"] and SHA.fullmatch(pr["merge_commit_sha"] or ""), "Merge is not confirmed")
        merged = self.api(f"git/commits/{pr['merge_commit_sha']}")
        require([p["sha"] for p in merged["parents"]] == [s["base"]]
                and merged["tree"]["sha"] == command("git", "rev-parse", f"{s['head']}^{{tree}}"),
                "Merged commit differs from the reviewed squash")
        s["merged"] = pr["merge_commit_sha"]
        s.pop("merge_pending", None)

    def main_ci(self):
        require(self.pr()["merge_commit_sha"] == self.state["merged"], "Merged SHA changed")
        run, attempt = self.watch(main=True)
        self.state.update(main_run=run, main_attempt=attempt)

    def cleanup(self):
        s = self.state
        pr = self.pr()
        require(pr["merged"] and pr["merge_commit_sha"] == s["merged"], "Merge is not confirmed")
        require(self.success(s["main_run"], main=True)[0] == s["main_attempt"], "main CI attempt changed")
        url = f"https://github.com/{self.repo}.git"
        ref = f"refs/heads/{s['branch']}"
        current = command("git", "ls-remote", "--refs", url, ref)
        if current:
            owner = self.repo.split("/")[0]
            require(not self.api("pulls", "--method", "GET", "-f", "state=open",
                                 "-f", f"head={owner}:{s['branch']}"),
                    "Work branch has an open PR")
            require(current == f"{s['head']}\t{ref}", "Work branch advanced; keep it")
            command("git", "push", "--no-follow-tags", "--recurse-submodules=no", f"--force-with-lease={ref}:{s['head']}", url, f":{ref}")
        require(not command("git", "ls-remote", "--refs", url, ref), "Remote work branch still exists")

    def execute(self):
        step = self.args.step
        if self.args.run is not None:
            require(step in {"wait", "verify-pr", "main-ci"}, "--run is only used by wait, verify-pr and main-ci")
            wait_step = "wait" if step == "verify-pr" else step
            if wait_step in self.state.get("done", {}):
                key = "main_run" if step == "main-ci" else "run"
                require(self.args.run == self.state[key], "--run differs from journal")
        if step != "verify-pr":
            return self.execute_step(step)

        require(self.args.run and self.args.run > 0, "Specify the target --run ID")
        result = "already completed"
        for stage in ("wait", "artifacts"):
            try:
                if self.execute_step(stage) == "completed":
                    result = "completed"
            except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
                message = str(error) if type(error) is ValueError else type(error).__name__
                raise ValueError(f"{stage}: {message}") from error
        return result

    def execute_step(self, step):
        done = self.state.get("done", {})
        if step in done:
            return "already completed"
        require(tuple(done) == STEPS[:STEPS.index(step)], "Complete the previous journal step first")
        if step in WRITES:
            require(self.args.apply, "This step needs --apply after authorization")
        timing_start = time.monotonic()
        timing = self.start_timing(step)
        start = time.monotonic()
        outcome = "failed"
        try:
            getattr(self, step.replace("-", "_"))()
            self.state["done"][step] = round(time.monotonic() - start, 3)
            self.save()
            outcome = "completed"
        except KeyboardInterrupt:
            outcome = "interrupted"
            raise
        finally:
            if timing is not None:
                timing["attempts"][-1].update(status=outcome, ended_utc=datetime.now(timezone.utc).isoformat(),
                                              elapsed_seconds=round(time.monotonic() - timing_start, 3))
                try:
                    save_json(timing_path(self.path), timing)
                except OSError:
                    print("Timing could not be finalized; inspect the integration journal", file=sys.stderr)
        return "completed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=(*STEPS, "verify-pr"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--repo")
    parser.add_argument("--head")
    parser.add_argument("--run", type=int)
    parser.add_argument("--title")
    parser.add_argument("--body-file", type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--record-timing", action="store_true",
                        help="Keep UTC intervals and elapsed time for each attempted step")
    args = parser.parse_args()
    try:
        require(args.timeout > 0, "Timeout must be positive")
        path = args.state.resolve()
        require(path.is_relative_to(Path(".local").absolute()), "Keep the journal under .local/")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(path.suffix + ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            work = Integration(path, args)
            result = work.execute()
            summary = {key: work.state[key] for key in
                       ("head", "base", "pr", "run", "attempt", "evidence", "merged", "main_run", "done")
                       if key in work.state}
            if args.step == "verify-pr":
                summary["verify"] = "success"
            print(json.dumps(dict(step=args.step, result=result, **summary)))
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        # Avoid printing values from untrusted responses and local file paths.
        message = str(error) if type(error) is ValueError else type(error).__name__
        print(f"{args.step} stopped: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
