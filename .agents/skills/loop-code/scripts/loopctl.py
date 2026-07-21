#!/usr/bin/env python3
"""Machine evidence, fingerprints, and stop decisions for loop-code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


EXIT_CODES = {
    "STOP_SUCCESS": 0,
    "CONTINUE": 10,
    "STOP_BUDGET": 31,
    "STALE_INPUT": 33,
    "STOP_SAFETY": 40,
}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def contract_view(ledger: dict) -> dict:
    acceptance = []
    for item in ledger.get("acceptance", []):
        if isinstance(item, dict):
            acceptance.append(
                {
                    key: value
                    for key, value in item.items()
                    if key not in {"status", "evidence_files", "user_accepted", "human_evidence"}
                }
            )
        else:
            acceptance.append(item)
    baseline = ledger.get("baseline", {})
    authority = ledger.get("authority", {})
    return {
        "task_id": ledger.get("task_id"),
        "objective": ledger.get("objective"),
        "scope": ledger.get("scope"),
        "baseline": {
            key: baseline.get(key)
            for key in ("revision", "environment", "protected_inputs", "rollback")
        },
        "authority": {key: value for key, value in authority.items() if key != "blocked"},
        "limits": ledger.get("limits"),
        "acceptance": acceptance,
    }


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"expected an exact file, not a directory: {path}")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def git_head(workspace: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        check=False,
    )
    return result.stdout.decode(errors="replace").strip() if result.returncode == 0 else None


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def display_path(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def workspace_for(ledger: dict, fallback: Path) -> Path:
    value = ledger.get("baseline", {}).get("workspace")
    return resolve_from(fallback, value).resolve() if value else fallback.resolve()


def capture_fingerprint(ledger_path: Path, workspace: Path, scope: list[str], pin_head: bool) -> dict:
    workspace = workspace.resolve()
    ledger_path = resolve_from(workspace, str(ledger_path))
    ledger = read_json(ledger_path)
    hashes = {}
    for value in scope:
        path = resolve_from(workspace, value)
        hashes[display_path(workspace, path)] = file_hash(path)
    revision = git_head(workspace) if pin_head else None
    if pin_head and revision is None:
        raise ValueError("--pin-head requires a Git repository with HEAD")
    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "base_revision": revision,
        "contract_sha256": digest(contract_view(ledger)),
        "scope_sha256": hashes,
    }


def verify_fingerprint(ledger_path: Path, workspace: Path, expected: dict) -> list[str]:
    current = capture_fingerprint(
        ledger_path,
        workspace,
        list(expected.get("scope_sha256", {}).keys()),
        expected.get("base_revision") is not None,
    )
    return [
        key
        for key in ("base_revision", "contract_sha256", "scope_sha256")
        if current.get(key) != expected.get(key)
    ]


def verifier_view(acceptance: dict) -> dict:
    verifier = acceptance.get("verifier", {})
    return {
        "type": verifier.get("type"),
        "argv": verifier.get("argv"),
        "cwd": verifier.get("cwd", "."),
        "timeout_seconds": verifier.get("timeout_seconds", 300),
        "expected_exit_code": verifier.get("expected_exit_code", 0),
    }


def find_acceptance(ledger: dict, acceptance_id: str) -> dict:
    matches = [item for item in ledger.get("acceptance", []) if isinstance(item, dict) and item.get("id") == acceptance_id]
    if len(matches) != 1:
        raise ValueError(f"acceptance id must exist exactly once: {acceptance_id}")
    return matches[0]


def artifact_hashes(acceptance: dict, workspace: Path) -> dict[str, str | None]:
    return {
        display_path(workspace, path): file_hash(path)
        for path in (resolve_from(workspace, value) for value in acceptance.get("artifacts", []))
    }


def bounded_tail(value: bytes | str | None, limit: int = 2000) -> str:
    if value is None:
        return ""
    text = value.decode(errors="replace") if isinstance(value, bytes) else value
    return text[-limit:]


def run_acceptance(ledger_path: Path, acceptance_id: str, output: Path | None = None) -> tuple[bool, Path]:
    ledger_path = ledger_path.resolve()
    ledger = read_json(ledger_path)
    acceptance = find_acceptance(ledger, acceptance_id)
    verifier = verifier_view(acceptance)
    if verifier["type"] != "command":
        raise ValueError(f"acceptance {acceptance_id} is not a command verifier")
    argv = verifier["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(value, str) and value for value in argv):
        raise ValueError("verifier.argv must be a non-empty string array")
    timeout = verifier["timeout_seconds"]
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive integer")

    workspace = workspace_for(ledger, ledger_path.parent)
    cwd = resolve_from(workspace, verifier["cwd"])
    try:
        cwd.relative_to(workspace)
    except ValueError as error:
        raise ValueError("verifier.cwd must stay inside baseline.workspace") from error
    if not cwd.is_dir():
        raise ValueError(f"verifier.cwd does not exist: {cwd}")

    started = datetime.now(timezone.utc)
    timed_out = False
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, check=False)
        exit_code = result.returncode
        stdout, stderr = result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exit_code = None
        stdout, stderr = error.stdout, error.stderr
    finished = datetime.now(timezone.utc)
    artifacts = artifact_hashes(acceptance, workspace)
    passed = (
        not timed_out
        and exit_code == verifier["expected_exit_code"]
        and all(value is not None for value in artifacts.values())
    )

    evidence = {
        "schema_version": 1,
        "acceptance_id": acceptance_id,
        "contract_sha256": digest(contract_view(ledger)),
        "verifier": verifier,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout_sha256": hashlib.sha256(stdout or b"").hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr or b"").hexdigest(),
        "stdout_tail": bounded_tail(stdout),
        "stderr_tail": bounded_tail(stderr),
        "artifacts_sha256": artifacts,
        "passed": passed,
    }
    if output is None:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", acceptance_id)
        stamp = finished.strftime("%Y%m%dT%H%M%S%fZ")
        output = ledger_path.parent / "evidence" / f"{safe_id}-{stamp}.json"
    else:
        output = output.resolve()
    write_json(output, evidence)

    evidence_files = acceptance.setdefault("evidence_files", [])
    evidence_files.append(display_path(ledger_path.parent, output))
    acceptance["status"] = "passed" if passed else "failed"
    write_json(ledger_path, ledger)
    return passed, output


def command_evidence_state(ledger: dict, ledger_path: Path, acceptance: dict) -> str:
    files = acceptance.get("evidence_files", [])
    if acceptance.get("status") != "passed" or not files:
        return "open"
    workspace = workspace_for(ledger, ledger_path.parent)
    expected_contract = digest(contract_view(ledger))
    expected_verifier = verifier_view(acceptance)
    current_artifacts = artifact_hashes(acceptance, workspace)
    for value in reversed(files):
        path = resolve_from(ledger_path.parent, value)
        try:
            evidence = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            evidence.get("acceptance_id") == acceptance.get("id")
            and evidence.get("passed") is True
            and evidence.get("contract_sha256") == expected_contract
            and evidence.get("verifier") == expected_verifier
            and evidence.get("artifacts_sha256") == current_artifacts
        ):
            return "passed"
    return "stale"


def acceptance_state(ledger: dict, ledger_path: Path, acceptance: object) -> str:
    if not isinstance(acceptance, dict):
        return "open"
    verifier_type = acceptance.get("verifier", {}).get("type")
    if verifier_type == "command":
        return command_evidence_state(ledger, ledger_path, acceptance)
    if verifier_type == "human":
        if (
            acceptance.get("status") == "passed"
            and acceptance.get("user_accepted") is True
            and bool(acceptance.get("human_evidence"))
        ):
            return "passed"
        return "open"
    return "open"


def is_open_critical(unknown: object) -> bool:
    if not isinstance(unknown, dict) or unknown.get("impact") != "critical":
        return False
    status = unknown.get("status", "open")
    if status in {"verified", "falsified", "resolved"}:
        return False
    return not (status == "accepted-risk" and unknown.get("user_accepted") is True)


def deadline_reached(value: object, now: datetime) -> bool:
    if not value:
        return False
    deadline = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return now >= deadline.astimezone(timezone.utc)


def stop_state(ledger: dict, ledger_path: Path, now: datetime | None = None) -> str:
    control = ledger.get("control", {})
    authority = ledger.get("authority", {})
    if control.get("safety_stop") is True or authority.get("blocked") is True:
        return "STOP_SAFETY"

    states = [acceptance_state(ledger, ledger_path, item) for item in ledger.get("acceptance", [])]
    if "stale" in states:
        return "STALE_INPUT"

    critical = [item for item in ledger.get("unknowns", []) if is_open_critical(item)]
    if states and all(state == "passed" for state in states) and not critical:
        return "STOP_SUCCESS"

    limits = ledger.get("limits", {})
    progress = ledger.get("progress", {})
    iteration = progress.get("iteration", 0)
    maximum = limits.get("max_iterations")
    current_time = now or datetime.now(timezone.utc)
    if (
        control.get("budget_exhausted") is True
        or (isinstance(maximum, int) and iteration >= maximum)
        or deadline_reached(limits.get("deadline"), current_time)
    ):
        return "STOP_BUDGET"
    return "CONTINUE"


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        ledger_path = root / "loop-ledger.json"
        output = root / "result.txt"
        ledger = {
            "schema_version": 3,
            "task_id": "test",
            "objective": "create verified output",
            "scope": {"in": [], "out": [], "interfaces": []},
            "baseline": {"workspace": str(root), "revision": None, "environment": {}, "protected_inputs": [], "rollback": ""},
            "authority": {"blocked": False},
            "limits": {"max_iterations": 3, "deadline": None},
            "control": {"safety_stop": False, "budget_exhausted": False},
            "progress": {"iteration": 1},
            "acceptance": [{
                "id": "AC-1",
                "criterion": "output exists",
                "verifier": {
                    "type": "command",
                    "argv": [sys.executable, "-c", "from pathlib import Path; Path('result.txt').write_text('ok')"],
                    "cwd": ".",
                    "timeout_seconds": 30,
                    "expected_exit_code": 0,
                },
                "artifacts": ["result.txt"],
                "status": "open",
                "evidence_files": [],
            }],
            "unknowns": [],
        }
        write_json(ledger_path, ledger)
        passed, _ = run_acceptance(ledger_path, "AC-1")
        assert passed and stop_state(read_json(ledger_path), ledger_path) == "STOP_SUCCESS"
        snapshot = capture_fingerprint(ledger_path, root, ["result.txt"], False)
        assert verify_fingerprint(ledger_path, root, snapshot) == []
        output.write_text("changed", encoding="utf-8")
        assert stop_state(read_json(ledger_path), ledger_path) == "STALE_INPUT"

        ledger = read_json(ledger_path)
        ledger["acceptance"][0].update({"status": "open", "evidence_files": []})
        ledger["control"]["safety_stop"] = True
        write_json(ledger_path, ledger)
        assert stop_state(read_json(ledger_path), ledger_path) == "STOP_SAFETY"
        ledger["control"]["safety_stop"] = False
        ledger["progress"]["iteration"] = 3
        write_json(ledger_path, ledger)
        assert stop_state(read_json(ledger_path), ledger_path) == "STOP_BUDGET"
        ledger["progress"]["iteration"] = 2
        write_json(ledger_path, ledger)
        assert stop_state(read_json(ledger_path), ledger_path) == "CONTINUE"

    print("SELF_TEST_OK")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    commands = parser.add_subparsers(dest="command")

    fingerprint = commands.add_parser("fingerprint")
    fingerprint_commands = fingerprint.add_subparsers(dest="fingerprint_command")
    capture = fingerprint_commands.add_parser("capture")
    capture.add_argument("--ledger", required=True)
    capture.add_argument("--workspace", default=".")
    capture.add_argument("--scope", nargs="*", default=[])
    capture.add_argument("--pin-head", action="store_true")
    capture.add_argument("--output")
    verify = fingerprint_commands.add_parser("verify")
    verify.add_argument("--ledger", required=True)
    verify.add_argument("--snapshot", required=True)
    verify.add_argument("--workspace", default=".")

    run = commands.add_parser("run")
    run.add_argument("ledger")
    run.add_argument("--acceptance", required=True)
    run.add_argument("--output")

    stop = commands.add_parser("stop")
    stop.add_argument("ledger")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        if args.command == "fingerprint" and args.fingerprint_command == "capture":
            snapshot = capture_fingerprint(Path(args.ledger), Path(args.workspace), args.scope, args.pin_head)
            if args.output:
                write_json(Path(args.output), snapshot)
            else:
                print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            return 0
        if args.command == "fingerprint" and args.fingerprint_command == "verify":
            expected = read_json(Path(args.snapshot))
            mismatches = verify_fingerprint(Path(args.ledger), Path(args.workspace), expected)
            if mismatches:
                print("STALE_INPUT " + ",".join(mismatches))
                return EXIT_CODES["STALE_INPUT"]
            print("MATCH")
            return 0
        if args.command == "run":
            passed, output = run_acceptance(Path(args.ledger), args.acceptance, Path(args.output) if args.output else None)
            print(f"{'VERIFY_PASS' if passed else 'VERIFY_FAIL'} {args.acceptance} {output}")
            return 0 if passed else 4
        if args.command == "stop":
            ledger_path = Path(args.ledger).resolve()
            state = stop_state(read_json(ledger_path), ledger_path)
            print(state)
            return EXIT_CODES[state]
        parser.print_help()
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"INVALID_INPUT {error}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
