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


def require_string(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        suffix = " with content" if not allow_empty else ""
        raise ValueError(f"{label} must be a string{suffix}")
    return value


def require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a string array")
    return value


def parse_deadline(value: object) -> datetime | None:
    if value is None:
        return None
    require_string(value, "limits.deadline")
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("limits.deadline must be an ISO-8601 datetime") from error
    return deadline.replace(tzinfo=timezone.utc) if deadline.tzinfo is None else deadline.astimezone(timezone.utc)


def validate_ledger(ledger: dict) -> None:
    if ledger.get("schema_version") != 3:
        raise ValueError("schema_version must be 3")
    require_string(ledger.get("task_id"), "task_id")
    require_string(ledger.get("objective"), "objective")

    scope = ledger.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope must be an object")
    for key in ("in", "out", "interfaces"):
        require_string_list(scope.get(key), f"scope.{key}")

    baseline = ledger.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")
    require_string(baseline.get("workspace"), "baseline.workspace")
    if baseline.get("revision") is not None:
        require_string(baseline["revision"], "baseline.revision")
    if not isinstance(baseline.get("environment"), dict):
        raise ValueError("baseline.environment must be an object")
    require_string_list(baseline.get("protected_inputs"), "baseline.protected_inputs")
    require_string(baseline.get("rollback"), "baseline.rollback", allow_empty=True)

    authority = ledger.get("authority")
    if not isinstance(authority, dict) or not isinstance(authority.get("blocked"), bool):
        raise ValueError("authority.blocked must be boolean")
    for key in ("allowed_writes", "forbidden_actions", "requires_user_approval"):
        if key in authority:
            require_string_list(authority[key], f"authority.{key}")

    limits = ledger.get("limits")
    if not isinstance(limits, dict) or "max_iterations" not in limits or "deadline" not in limits:
        raise ValueError("limits must contain max_iterations and deadline")
    maximum = limits["max_iterations"]
    if maximum is not None and (isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0):
        raise ValueError("limits.max_iterations must be null or a positive integer")
    parse_deadline(limits["deadline"])
    if maximum is None and limits["deadline"] is None:
        raise ValueError("at least one iteration or deadline limit is required")

    progress = ledger.get("progress")
    iteration = progress.get("iteration") if isinstance(progress, dict) else None
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0:
        raise ValueError("progress.iteration must be a non-negative integer")

    control = ledger.get("control")
    if not isinstance(control, dict):
        raise ValueError("control must be an object")
    for key in ("safety_stop", "budget_exhausted"):
        if not isinstance(control.get(key), bool):
            raise ValueError(f"control.{key} must be boolean")

    acceptance = ledger.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        raise ValueError("acceptance must be a non-empty array")
    acceptance_ids = set()
    for index, item in enumerate(acceptance):
        label = f"acceptance[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        acceptance_id = require_string(item.get("id"), f"{label}.id")
        if acceptance_id in acceptance_ids:
            raise ValueError(f"acceptance id must be unique: {acceptance_id}")
        acceptance_ids.add(acceptance_id)
        require_string(item.get("criterion"), f"{label}.criterion")
        require_string_list(item.get("artifacts"), f"{label}.artifacts")
        if item.get("status") not in {"open", "passed", "failed"}:
            raise ValueError(f"{label}.status must be open, passed, or failed")
        if "evidence_files" in item:
            require_string_list(item["evidence_files"], f"{label}.evidence_files")
        verifier = item.get("verifier")
        if not isinstance(verifier, dict) or verifier.get("type") not in {"command", "human"}:
            raise ValueError(f"{label}.verifier.type must be command or human")
        if verifier["type"] == "command":
            require_string_list(verifier.get("argv"), f"{label}.verifier.argv")
            require_string(verifier.get("cwd", "."), f"{label}.verifier.cwd")
            timeout = verifier.get("timeout_seconds", 300)
            if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
                raise ValueError(f"{label}.verifier.timeout_seconds must be a positive integer")
            expected_exit = verifier.get("expected_exit_code", 0)
            if isinstance(expected_exit, bool) or not isinstance(expected_exit, int):
                raise ValueError(f"{label}.verifier.expected_exit_code must be an integer")
        else:
            require_string(verifier.get("instructions"), f"{label}.verifier.instructions")
            if not isinstance(item.get("user_accepted"), bool):
                raise ValueError(f"{label}.user_accepted must be boolean")
            require_string(item.get("human_evidence"), f"{label}.human_evidence", allow_empty=True)
            if "fingerprint_snapshot" in item:
                require_string(item["fingerprint_snapshot"], f"{label}.fingerprint_snapshot")

    unknowns = ledger.get("unknowns")
    if not isinstance(unknowns, list):
        raise ValueError("unknowns must be an array")
    unknown_ids = set()
    for index, item in enumerate(unknowns):
        label = f"unknowns[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        unknown_id = require_string(item.get("id"), f"{label}.id")
        if unknown_id in unknown_ids:
            raise ValueError(f"unknown id must be unique: {unknown_id}")
        unknown_ids.add(unknown_id)
        status = item.get("status", "open")
        if item.get("impact") == "critical" and status in {"verified", "falsified", "resolved"}:
            if not isinstance(item.get("evidence"), list) or not item["evidence"]:
                raise ValueError(f"{label} requires evidence before closing")
        if item.get("impact") == "critical" and status == "accepted-risk" and item.get("user_accepted") is not True:
            raise ValueError(f"{label} accepted-risk requires user_accepted")


def contract_view(ledger: dict) -> dict:
    acceptance = []
    for item in ledger.get("acceptance", []):
        if isinstance(item, dict):
            acceptance.append(
                {
                    key: value
                    for key, value in item.items()
                    if key not in {
                        "status",
                        "evidence_files",
                        "user_accepted",
                        "human_evidence",
                        "fingerprint_snapshot",
                    }
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
            for key in ("workspace", "revision", "environment", "protected_inputs", "rollback")
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
    validate_ledger(ledger)
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
    if not isinstance(expected.get("scope_sha256"), dict):
        raise ValueError("fingerprint scope_sha256 must be an object")
    current = capture_fingerprint(
        ledger_path,
        workspace,
        list(expected.get("scope_sha256", {}).keys()),
        expected.get("base_revision") is not None,
    )
    return [
        key
        for key in ("workspace", "base_revision", "contract_sha256", "scope_sha256")
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
    validate_ledger(ledger)
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

    input_fingerprint = capture_fingerprint(
        ledger_path,
        workspace,
        ledger["baseline"]["protected_inputs"],
        False,
    )
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
        # A declared protected input that no longer hashes is a missing input, not a pass.
        # Without this the verifier stays green after an input is deleted, moved, or never
        # checked out, and the evidence records null beside "passed".
        and all(value is not None for value in input_fingerprint["scope_sha256"].values())
    )

    evidence = {
        "schema_version": 2,
        "acceptance_id": acceptance_id,
        "contract_sha256": digest(contract_view(ledger)),
        "input_fingerprint": input_fingerprint,
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
        fingerprint = evidence.get("input_fingerprint")
        try:
            fingerprint_is_current = isinstance(fingerprint, dict) and not verify_fingerprint(
                ledger_path, workspace, fingerprint
            )
        except (OSError, ValueError, json.JSONDecodeError):
            fingerprint_is_current = False
        if (
            evidence.get("acceptance_id") == acceptance.get("id")
            and evidence.get("passed") is True
            and evidence.get("contract_sha256") == expected_contract
            and evidence.get("verifier") == expected_verifier
            and evidence.get("artifacts_sha256") == current_artifacts
            and fingerprint_is_current
        ):
            return "passed"
    return "stale"


def human_evidence_state(ledger: dict, ledger_path: Path, acceptance: dict) -> str:
    if (
        acceptance.get("status") != "passed"
        or acceptance.get("user_accepted") is not True
        or not acceptance.get("human_evidence")
    ):
        return "open"
    workspace = workspace_for(ledger, ledger_path.parent)
    required = ledger["baseline"]["protected_inputs"] + acceptance.get("artifacts", [])
    if not required:
        return "passed"
    snapshot_value = acceptance.get("fingerprint_snapshot")
    if not snapshot_value:
        return "stale"
    try:
        snapshot = read_json(resolve_from(ledger_path.parent, snapshot_value))
        expected_paths = {
            display_path(workspace, resolve_from(workspace, value))
            for value in required
        }
        captured_paths = snapshot.get("scope_sha256", {})
        if not isinstance(captured_paths, dict) or not expected_paths.issubset(captured_paths):
            return "stale"
        return "stale" if verify_fingerprint(ledger_path, workspace, snapshot) else "passed"
    except (OSError, ValueError, json.JSONDecodeError):
        return "stale"


def acceptance_state(ledger: dict, ledger_path: Path, acceptance: object) -> str:
    if not isinstance(acceptance, dict):
        return "open"
    verifier_type = acceptance.get("verifier", {}).get("type")
    if verifier_type == "command":
        return command_evidence_state(ledger, ledger_path, acceptance)
    if verifier_type == "human":
        return human_evidence_state(ledger, ledger_path, acceptance)
    return "open"


def is_open_critical(unknown: object) -> bool:
    if not isinstance(unknown, dict) or unknown.get("impact") != "critical":
        return False
    status = unknown.get("status", "open")
    if status in {"verified", "falsified", "resolved"}:
        return not (isinstance(unknown.get("evidence"), list) and bool(unknown["evidence"]))
    return not (status == "accepted-risk" and unknown.get("user_accepted") is True)


def deadline_reached(value: object, now: datetime) -> bool:
    deadline = parse_deadline(value)
    return deadline is not None and now >= deadline


def stop_state(ledger: dict, ledger_path: Path, now: datetime | None = None) -> str:
    validate_ledger(ledger)
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

        source = root / "source.txt"
        source.write_text("before", encoding="utf-8")
        ledger["baseline"]["protected_inputs"] = ["source.txt"]
        ledger["acceptance"][0].update({
            "verifier": {
                "type": "command",
                "argv": [sys.executable, "-c", "pass"],
                "cwd": ".",
                "timeout_seconds": 30,
                "expected_exit_code": 0,
            },
            "artifacts": [],
            "status": "open",
            "evidence_files": [],
        })
        write_json(ledger_path, ledger)
        assert run_acceptance(ledger_path, "AC-1")[0]
        source.write_text("after", encoding="utf-8")
        assert stop_state(read_json(ledger_path), ledger_path) == "STALE_INPUT"

        source.write_text("current", encoding="utf-8")
        ledger = read_json(ledger_path)
        ledger["acceptance"][0].update({"status": "open", "evidence_files": []})
        write_json(ledger_path, ledger)
        assert run_acceptance(ledger_path, "AC-1")[0]
        ledger = read_json(ledger_path)
        other_workspace = root / "other"
        other_workspace.mkdir()
        ledger["baseline"]["workspace"] = str(other_workspace)
        write_json(ledger_path, ledger)
        assert stop_state(read_json(ledger_path), ledger_path) == "STALE_INPUT"

        ledger["baseline"]["workspace"] = str(root)
        ledger["unknowns"] = [{
            "id": "KU-1",
            "impact": "critical",
            "status": "resolved",
            "evidence": [],
        }]
        write_json(ledger_path, ledger)
        try:
            stop_state(read_json(ledger_path), ledger_path)
        except ValueError:
            pass
        else:
            raise AssertionError("critical unknown closed without evidence")

        ledger["unknowns"] = []
        ledger["objective"] = ""
        write_json(ledger_path, ledger)
        try:
            stop_state(read_json(ledger_path), ledger_path)
        except ValueError:
            pass
        else:
            raise AssertionError("blank objective accepted")

        ledger["objective"] = "review verified output"
        ledger["limits"] = {"max_iterations": None, "deadline": None}
        write_json(ledger_path, ledger)
        try:
            stop_state(read_json(ledger_path), ledger_path)
        except ValueError:
            pass
        else:
            raise AssertionError("unbounded ledger accepted")

        reviewed = root / "review.txt"
        reviewed.write_text("approved", encoding="utf-8")
        snapshot_path = root / "human-fingerprint.json"
        ledger["limits"] = {"max_iterations": 3, "deadline": None}
        ledger["acceptance"] = [{
            "id": "AC-H",
            "criterion": "user approves reviewed output",
            "verifier": {
                "type": "human",
                "instructions": "Inspect source.txt and review.txt",
            },
            "artifacts": ["review.txt"],
            "status": "passed",
            "user_accepted": True,
            "human_evidence": "User approved the reviewed files.",
            "fingerprint_snapshot": "human-fingerprint.json",
        }]
        write_json(ledger_path, ledger)
        snapshot = capture_fingerprint(ledger_path, root, ["source.txt", "review.txt"], False)
        write_json(snapshot_path, snapshot)
        assert stop_state(read_json(ledger_path), ledger_path) == "STOP_SUCCESS"
        reviewed.write_text("changed", encoding="utf-8")
        assert stop_state(read_json(ledger_path), ledger_path) == "STALE_INPUT"

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
