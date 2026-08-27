#!/usr/bin/env python3
"""Machine evidence, fingerprints, and stop decisions for loop-code."""

from __future__ import annotations

import argparse
import copy
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
    "WAITING_HUMAN": 20,
    "STOP_BUDGET": 31,
    "STALE_INPUT": 33,
    "STOP_SAFETY": 40,
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
LEGACY_HASH_RE = re.compile(r"^(?P<path>.+?) \(SHA256 (?P<sha>[0-9a-fA-F]{64})\)$")


class StaleInputError(ValueError):
    pass


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


def require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def require_string(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        suffix = " with content" if not allow_empty else ""
        raise ValueError(f"{label} must be a string{suffix}")
    return value


def require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a string array")
    return value


def normalize_legacy_string_list(value: object, label: str, notes: list[str]) -> list[str]:
    if isinstance(value, str) and value:
        notes.append(f"{label}: wrapped legacy scalar text in an array")
        return [value]
    if isinstance(value, dict):
        notes.append(f"{label}: wrapped structured legacy value as canonical JSON text")
        return [json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]
    if not isinstance(value, list):
        raise ValueError(f"{label} cannot be normalized without guessing")
    result = []
    for index, item in enumerate(value):
        if isinstance(item, str) and item:
            result.append(item)
        elif isinstance(item, (dict, list)):
            result.append(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            notes.append(f"{label}[{index}]: preserved structured legacy value as canonical JSON text")
        else:
            raise ValueError(f"{label}[{index}] cannot be normalized without guessing")
    return result


def reject_unknown_keys(value: dict, allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"{label} contains unknown key(s): {', '.join(unknown)}")


def parse_deadline(value: object, label: str = "limits.deadline") -> datetime | None:
    if value is None:
        return None
    require_string(value, label)
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 datetime") from error
    return deadline.replace(tzinfo=timezone.utc) if deadline.tzinfo is None else deadline.astimezone(timezone.utc)


def normalize_legacy_protected(value: object, label: str, notes: list[str]) -> dict:
    text = require_string(value, label)
    match = LEGACY_HASH_RE.fullmatch(text)
    if match:
        notes.append(f"{label}: split legacy path/hash string")
        return {"path": match.group("path"), "sha256": match.group("sha").lower()}
    if re.search(r"\(\s*SHA256\b", text, re.IGNORECASE):
        raise ValueError(f"{label} has malformed legacy path/hash; expected 'path (SHA256 <64 hex>)'")
    notes.append(f"{label}: legacy path has no hash; freshness is not checked")
    return {"path": text, "sha256": None}


def normalize_legacy_unknown(item: object, index: int, notes: list[str]) -> dict:
    label = f"unknowns[{index}]"
    value = require_object(item, label)
    reject_unknown_keys(
        value,
        {"id", "class", "statement", "safe_probe", "type", "q", "probe", "impact", "status", "user_accepted", "evidence"},
        label,
    )
    aliases = (("class", "type"), ("statement", "q"), ("safe_probe", "probe"))
    normalized = {}
    for canonical, legacy in aliases:
        if canonical in value and legacy in value and value[canonical] != value[legacy]:
            raise ValueError(f"{label} has conflicting {canonical}/{legacy} aliases")
        normalized[canonical] = value.get(canonical, value.get(legacy, ""))
        if legacy in value:
            notes.append(f"{label}.{legacy}: normalized to {canonical}")
    impact = value.get("impact", "noncritical")
    if impact != "critical":
        if impact != "noncritical":
            notes.append(f"{label}.impact: normalized {impact!r} to 'noncritical'")
        impact = "noncritical"
    evidence = normalize_legacy_string_list(value.get("evidence", []), f"{label}.evidence", notes)
    status = value.get("status", "open")
    if status == "accepted-risk":
        if value.get("user_accepted") is True:
            if not evidence:
                evidence = ["legacy user_accepted=true (unauthenticated compatibility metadata)"]
                notes.append(f"{label}: preserved legacy accepted-risk without claiming actor authentication")
        else:
            status = "open"
            notes.append(f"{label}.status: reopened accepted-risk because legacy user_accepted was not true")
    return {
        "id": value.get("id", ""),
        "class": normalized["class"],
        "statement": normalized["statement"],
        "impact": impact,
        "status": status,
        "safe_probe": normalized["safe_probe"],
        "evidence": evidence,
    }


def normalize_legacy_decision(item: object, index: int, notes: list[str]) -> dict:
    if isinstance(item, str):
        return {"id": f"legacy-D-{index + 1}", "statement": item, "rationale": "", "evidence": []}
    label = f"decisions[{index}]"
    value = require_object(item, label)
    reject_unknown_keys(value, {"id", "statement", "reason", "decision", "what", "why", "evidence"}, label)
    return {
        "id": value.get("id", f"legacy-D-{index + 1}"),
        "statement": value.get("statement", value.get("decision", value.get("what", ""))),
        "rationale": value.get("reason", value.get("why", "")),
        "evidence": normalize_legacy_string_list(value.get("evidence", []), f"{label}.evidence", notes),
    }


def normalize_legacy_acceptance(item: object, index: int, notes: list[str]) -> dict:
    label = f"acceptance[{index}]"
    value = require_object(item, label)
    reject_unknown_keys(
        value,
        {"id", "criterion", "verifier", "artifacts", "status", "evidence_files", "user_accepted", "human_evidence", "fingerprint_snapshot"},
        label,
    )
    verifier = copy.deepcopy(require_object(value.get("verifier"), f"{label}.verifier"))
    if verifier.get("type") == "command":
        verifier.setdefault("cwd", ".")
        verifier.setdefault("timeout_seconds", 300)
        verifier.setdefault("expected_exit_code", 0)
    result = {
        "id": value.get("id", ""),
        "criterion": value.get("criterion", ""),
        "verifier": verifier,
        "artifacts": copy.deepcopy(value.get("artifacts", [])),
        "status": value.get("status", "open"),
        "evidence_files": copy.deepcopy(value.get("evidence_files", [])),
    }
    if verifier.get("type") == "human":
        accepted = value.get("user_accepted") is True
        result["attestation"] = {
            "accepted": accepted,
            "actor": "legacy-unspecified" if accepted else "",
            "attested_at": None,
            "statement": value.get("human_evidence", ""),
            "fingerprint_snapshot": value.get("fingerprint_snapshot"),
        }
        notes.append(f"{label}: normalized legacy human fields; actor is unauthenticated metadata")
    return result


def normalize_ledger(raw: dict) -> tuple[dict, dict | None, list[str]]:
    version = raw.get("schema_version")
    if version == 4:
        validate_ledger(raw)
        return raw, None, []
    if version != 3:
        raise ValueError("schema_version must be 3 or 4")

    reject_unknown_keys(
        raw,
        {"schema_version", "task_id", "objective", "scope", "baseline", "authority", "limits", "control", "progress", "acceptance", "unknowns", "decisions", "handoff"},
        "ledger",
    )
    notes = ["schema_version 3 normalized in memory; source remains unchanged"]
    baseline = require_object(raw.get("baseline"), "baseline")
    revision = baseline.get("revision")
    authority = require_object(raw.get("authority"), "authority")
    control = require_object(raw.get("control"), "control")
    progress = require_object(raw.get("progress"), "progress")
    handoff = require_object(raw.get("handoff", {}), "handoff")
    ledger = {
        "schema_version": 4,
        "task_id": raw.get("task_id", ""),
        "objective": raw.get("objective", ""),
        "scope": copy.deepcopy(raw.get("scope")),
        "baseline": {
            "workspace": baseline.get("workspace", ""),
            "revision": {"mode": "recorded" if revision is not None else "none", "value": revision},
            "environment": copy.deepcopy(baseline.get("environment", {})),
            "protected_inputs": [
                normalize_legacy_protected(item, f"baseline.protected_inputs[{index}]", notes)
                for index, item in enumerate(baseline.get("protected_inputs", []))
            ],
            "rollback": baseline.get("rollback", ""),
        },
        "authority": {
            "allowed_writes": copy.deepcopy(authority.get("allowed_writes", [])),
            "forbidden_actions": copy.deepcopy(authority.get("forbidden_actions", [])),
            "requires_user_approval": copy.deepcopy(authority.get("requires_user_approval", [])),
            "blocked": authority.get("blocked", False),
            "reasons": [],
        },
        "limits": copy.deepcopy(raw.get("limits")),
        "control": {
            "safety_stop": control.get("safety_stop", False),
            "budget_exhausted": control.get("budget_exhausted", False),
            "reasons": copy.deepcopy(control.get("reasons", [])),
        },
        "progress": {"iteration": progress.get("iteration", 0)},
        "acceptance": [normalize_legacy_acceptance(item, index, notes) for index, item in enumerate(raw.get("acceptance", []))],
        "unknowns": [normalize_legacy_unknown(item, index, notes) for index, item in enumerate(raw.get("unknowns", []))],
        "decisions": [normalize_legacy_decision(item, index, notes) for index, item in enumerate(raw.get("decisions", []))],
        "handoff": {
            "current_focus": handoff.get("current_focus", ""),
            "changed_paths": copy.deepcopy(handoff.get("changed_paths", [])),
            "failed_attempts": normalize_legacy_string_list(handoff.get("failed_attempts", []), "handoff.failed_attempts", notes),
            "blockers": copy.deepcopy(handoff.get("blockers", [])),
            "next_action": handoff.get("next_action", ""),
        },
    }
    validate_ledger(ledger, allow_legacy_attestation=True)
    return ledger, raw, notes


def load_ledger(path: Path) -> tuple[dict, dict | None, list[str]]:
    return normalize_ledger(read_json(path))


def validate_ledger(ledger: dict, *, allow_legacy_attestation: bool = False) -> None:
    if ledger.get("schema_version") != 4:
        raise ValueError("schema_version must be 4")
    reject_unknown_keys(
        ledger,
        {"schema_version", "task_id", "objective", "scope", "baseline", "authority", "limits", "control", "progress", "acceptance", "unknowns", "decisions", "handoff"},
        "ledger",
    )
    require_string(ledger.get("task_id"), "task_id")
    require_string(ledger.get("objective"), "objective")

    scope = require_object(ledger.get("scope"), "scope")
    reject_unknown_keys(scope, {"in", "out", "interfaces"}, "scope")
    for key in ("in", "out", "interfaces"):
        require_string_list(scope.get(key), f"scope.{key}")

    baseline = require_object(ledger.get("baseline"), "baseline")
    reject_unknown_keys(baseline, {"workspace", "revision", "environment", "protected_inputs", "rollback"}, "baseline")
    require_string(baseline.get("workspace"), "baseline.workspace")
    revision = require_object(baseline.get("revision"), "baseline.revision")
    reject_unknown_keys(revision, {"mode", "value"}, "baseline.revision")
    if revision.get("mode") not in {"none", "recorded", "exact"}:
        raise ValueError("baseline.revision.mode must be none, recorded, or exact")
    if revision["mode"] == "none":
        if revision.get("value") is not None:
            raise ValueError("baseline.revision.value must be null when mode is none")
    else:
        require_string(revision.get("value"), "baseline.revision.value")
    if not isinstance(baseline.get("environment"), dict):
        raise ValueError("baseline.environment must be an object")
    protected = baseline.get("protected_inputs")
    if not isinstance(protected, list):
        raise ValueError("baseline.protected_inputs must be an array")
    for index, item in enumerate(protected):
        label = f"baseline.protected_inputs[{index}]"
        value = require_object(item, label)
        reject_unknown_keys(value, {"path", "sha256"}, label)
        require_string(value.get("path"), f"{label}.path")
        sha256 = value.get("sha256")
        if sha256 is None and allow_legacy_attestation:
            continue
        if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
            raise ValueError(f"{label}.sha256 must be 64 lowercase hex characters")
    require_string(baseline.get("rollback"), "baseline.rollback", allow_empty=True)

    authority = require_object(ledger.get("authority"), "authority")
    reject_unknown_keys(authority, {"allowed_writes", "forbidden_actions", "requires_user_approval", "blocked", "reasons"}, "authority")
    for key in ("allowed_writes", "forbidden_actions", "requires_user_approval", "reasons"):
        require_string_list(authority.get(key), f"authority.{key}")
    if not isinstance(authority.get("blocked"), bool):
        raise ValueError("authority.blocked must be boolean")

    limits = require_object(ledger.get("limits"), "limits")
    reject_unknown_keys(limits, {"max_iterations", "deadline"}, "limits")
    maximum = limits.get("max_iterations")
    if maximum is not None and (isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0):
        raise ValueError("limits.max_iterations must be null or a positive integer")
    parse_deadline(limits.get("deadline"))
    if maximum is None and limits.get("deadline") is None:
        raise ValueError("at least one iteration or deadline limit is required")

    control = require_object(ledger.get("control"), "control")
    reject_unknown_keys(control, {"safety_stop", "budget_exhausted", "reasons"}, "control")
    for key in ("safety_stop", "budget_exhausted"):
        if not isinstance(control.get(key), bool):
            raise ValueError(f"control.{key} must be boolean")
    require_string_list(control.get("reasons"), "control.reasons")

    progress = require_object(ledger.get("progress"), "progress")
    reject_unknown_keys(progress, {"iteration"}, "progress")
    iteration = progress.get("iteration")
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 0:
        raise ValueError("progress.iteration must be a non-negative integer")

    acceptance = ledger.get("acceptance")
    if not isinstance(acceptance, list) or not acceptance:
        raise ValueError("acceptance must be a non-empty array")
    acceptance_ids = set()
    for index, item in enumerate(acceptance):
        label = f"acceptance[{index}]"
        value = require_object(item, label)
        allowed = {"id", "criterion", "verifier", "artifacts", "status", "evidence_files", "attestation"}
        reject_unknown_keys(value, allowed, label)
        acceptance_id = require_string(value.get("id"), f"{label}.id")
        if acceptance_id in acceptance_ids:
            raise ValueError(f"acceptance id must be unique: {acceptance_id}")
        acceptance_ids.add(acceptance_id)
        require_string(value.get("criterion"), f"{label}.criterion")
        require_string_list(value.get("artifacts"), f"{label}.artifacts")
        require_string_list(value.get("evidence_files"), f"{label}.evidence_files")
        if value.get("status") not in {"open", "passed", "failed"}:
            raise ValueError(f"{label}.status must be open, passed, or failed")
        verifier = require_object(value.get("verifier"), f"{label}.verifier")
        verifier_type = verifier.get("type")
        if verifier_type == "command":
            reject_unknown_keys(verifier, {"type", "argv", "cwd", "timeout_seconds", "expected_exit_code"}, f"{label}.verifier")
            argv = require_string_list(verifier.get("argv"), f"{label}.verifier.argv")
            if not argv:
                raise ValueError(f"{label}.verifier.argv must not be empty")
            require_string(verifier.get("cwd"), f"{label}.verifier.cwd")
            timeout = verifier.get("timeout_seconds")
            if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
                raise ValueError(f"{label}.verifier.timeout_seconds must be a positive integer")
            expected_exit = verifier.get("expected_exit_code")
            if isinstance(expected_exit, bool) or not isinstance(expected_exit, int):
                raise ValueError(f"{label}.verifier.expected_exit_code must be an integer")
            if "attestation" in value:
                raise ValueError(f"{label}.attestation is only valid for a human verifier")
            if value.get("status") == "passed" and not value["evidence_files"]:
                raise ValueError(f"{label} passed command requires evidence_files")
        elif verifier_type == "human":
            reject_unknown_keys(verifier, {"type", "instructions"}, f"{label}.verifier")
            require_string(verifier.get("instructions"), f"{label}.verifier.instructions")
            attestation = require_object(value.get("attestation"), f"{label}.attestation")
            reject_unknown_keys(attestation, {"accepted", "actor", "attested_at", "statement", "fingerprint_snapshot"}, f"{label}.attestation")
            if not isinstance(attestation.get("accepted"), bool):
                raise ValueError(f"{label}.attestation.accepted must be boolean")
            require_string(attestation.get("actor"), f"{label}.attestation.actor", allow_empty=True)
            require_string(attestation.get("statement"), f"{label}.attestation.statement", allow_empty=True)
            snapshot = attestation.get("fingerprint_snapshot")
            if snapshot is not None:
                require_string(snapshot, f"{label}.attestation.fingerprint_snapshot")
            if attestation["accepted"]:
                if value.get("status") != "passed":
                    raise ValueError(f"{label} accepted human attestation requires passed status")
                if not allow_legacy_attestation:
                    require_string(attestation.get("actor"), f"{label}.attestation.actor")
                    parse_deadline(attestation.get("attested_at"), f"{label}.attestation.attested_at")
                    require_string(attestation.get("statement"), f"{label}.attestation.statement")
                    require_string(snapshot, f"{label}.attestation.fingerprint_snapshot")
            elif value.get("status") == "passed":
                raise ValueError(f"{label} passed human acceptance requires accepted attestation")
        else:
            raise ValueError(f"{label}.verifier.type must be command or human")

    unknowns = ledger.get("unknowns")
    if not isinstance(unknowns, list):
        raise ValueError("unknowns must be an array")
    unknown_ids = set()
    for index, item in enumerate(unknowns):
        label = f"unknowns[{index}]"
        value = require_object(item, label)
        reject_unknown_keys(value, {"id", "class", "statement", "impact", "status", "safe_probe", "evidence"}, label)
        unknown_id = require_string(value.get("id"), f"{label}.id")
        if unknown_id in unknown_ids:
            raise ValueError(f"unknown id must be unique: {unknown_id}")
        unknown_ids.add(unknown_id)
        if value.get("class") not in {"KK", "KU", "UK", "UU"}:
            raise ValueError(f"{label}.class must be KK, KU, UK, or UU")
        require_string(value.get("statement"), f"{label}.statement")
        if value.get("impact") not in {"critical", "noncritical"}:
            raise ValueError(f"{label}.impact must be critical or noncritical")
        if value.get("status") not in {"open", "verified", "falsified", "resolved", "accepted-risk"}:
            raise ValueError(f"{label}.status has an unknown enum value")
        require_string(value.get("safe_probe"), f"{label}.safe_probe", allow_empty=True)
        evidence = require_string_list(value.get("evidence"), f"{label}.evidence")
        if value["impact"] == "critical" and value["status"] != "open" and not evidence:
            raise ValueError(f"{label} requires evidence before closing")

    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("decisions must be an array")
    decision_ids = set()
    for index, item in enumerate(decisions):
        label = f"decisions[{index}]"
        value = require_object(item, label)
        reject_unknown_keys(value, {"id", "statement", "rationale", "evidence"}, label)
        decision_id = require_string(value.get("id"), f"{label}.id")
        if decision_id in decision_ids:
            raise ValueError(f"decision id must be unique: {decision_id}")
        decision_ids.add(decision_id)
        require_string(value.get("statement"), f"{label}.statement")
        require_string(value.get("rationale"), f"{label}.rationale", allow_empty=True)
        require_string_list(value.get("evidence"), f"{label}.evidence")

    handoff = require_object(ledger.get("handoff"), "handoff")
    reject_unknown_keys(handoff, {"current_focus", "changed_paths", "failed_attempts", "blockers", "next_action"}, "handoff")
    require_string(handoff.get("current_focus"), "handoff.current_focus", allow_empty=True)
    for key in ("changed_paths", "failed_attempts", "blockers"):
        require_string_list(handoff.get(key), f"handoff.{key}")
    require_string(handoff.get("next_action"), "handoff.next_action", allow_empty=True)


def legacy_contract_view(ledger: dict) -> dict:
    acceptance = []
    for item in ledger.get("acceptance", []):
        acceptance.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"status", "evidence_files", "user_accepted", "human_evidence", "fingerprint_snapshot"}
            }
            if isinstance(item, dict)
            else item
        )
    baseline = ledger.get("baseline", {})
    authority = ledger.get("authority", {})
    return {
        "task_id": ledger.get("task_id"),
        "objective": ledger.get("objective"),
        "scope": ledger.get("scope"),
        "baseline": {key: baseline.get(key) for key in ("workspace", "revision", "environment", "protected_inputs", "rollback")},
        "authority": {key: value for key, value in authority.items() if key != "blocked"},
        "limits": ledger.get("limits"),
        "acceptance": acceptance,
    }


def contract_view(ledger: dict) -> dict:
    acceptance = []
    for item in ledger.get("acceptance", []):
        acceptance.append(
            {key: value for key, value in item.items() if key not in {"status", "evidence_files", "attestation"}}
            if isinstance(item, dict)
            else item
        )
    baseline = ledger.get("baseline", {})
    authority = ledger.get("authority", {})
    return {
        "schema_version": 4,
        "task_id": ledger.get("task_id"),
        "objective": ledger.get("objective"),
        "scope": ledger.get("scope"),
        "baseline": {key: baseline.get(key) for key in ("workspace", "revision", "environment", "protected_inputs", "rollback")},
        "authority": {key: value for key, value in authority.items() if key not in {"blocked", "reasons"}},
        "limits": ledger.get("limits"),
        "acceptance": acceptance,
    }


def contract_digest(ledger: dict, legacy: dict | None = None) -> str:
    return digest(legacy_contract_view(legacy) if legacy is not None else contract_view(ledger))


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
    result = subprocess.run(["git", "-C", str(workspace), "rev-parse", "--verify", "HEAD"], capture_output=True, check=False)
    return result.stdout.decode(errors="replace").strip() if result.returncode == 0 else None


def git_dirty(workspace: Path) -> bool | None:
    result = subprocess.run(
        ["git", "-C", str(workspace), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        check=False,
    )
    return bool(result.stdout) if result.returncode == 0 else None


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def display_path(base: Path, path: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def workspace_for(ledger: dict, fallback: Path) -> Path:
    return resolve_from(fallback, ledger["baseline"]["workspace"]).resolve()


def protected_paths(ledger: dict) -> list[str]:
    return [item["path"] for item in ledger["baseline"]["protected_inputs"]]


def capture_fingerprint(ledger_path: Path, workspace: Path, scope: list[str], pin_head: bool) -> dict:
    workspace = workspace.resolve()
    ledger_path = resolve_from(workspace, str(ledger_path))
    ledger, legacy, _ = load_ledger(ledger_path)
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
        "contract_sha256": contract_digest(ledger, legacy),
        "scope_sha256": hashes,
    }


def detail(facet: str, condition: str, **values: object) -> dict:
    return {"facet": facet, "condition": condition, **values}


def fingerprint_differences(ledger_path: Path, workspace: Path, expected: dict) -> list[dict]:
    expected_scope = expected.get("scope_sha256")
    if not isinstance(expected_scope, dict):
        raise ValueError("fingerprint scope_sha256 must be an object")
    ledger, legacy, _ = load_ledger(ledger_path)
    differences = []
    actual_workspace = str(workspace.resolve())
    if expected.get("workspace") != actual_workspace:
        differences.append(detail("workspace", "changed", expected=expected.get("workspace"), actual=actual_workspace))
    expected_revision = expected.get("base_revision")
    if expected_revision is not None:
        actual_revision = git_head(workspace)
        if expected_revision != actual_revision:
            differences.append(detail("revision", "changed" if actual_revision else "non_git", expected=expected_revision, actual=actual_revision))
    actual_contract = contract_digest(ledger, legacy)
    if expected.get("contract_sha256") != actual_contract:
        differences.append(detail("contract", "changed", expected=expected.get("contract_sha256"), actual=actual_contract))
    for value, expected_hash in expected_scope.items():
        path = resolve_from(workspace, value)
        try:
            actual_hash = file_hash(path)
            condition = "missing" if actual_hash is None else "changed"
        except ValueError:
            actual_hash = None
            condition = "not_file"
        if expected_hash is None:
            differences.append(detail("protected_input", "invalid_expected_hash", path=value, expected_sha256=None, actual_sha256=actual_hash))
        elif expected_hash != actual_hash:
            differences.append(detail("protected_input", condition, path=value, expected_sha256=expected_hash, actual_sha256=actual_hash))
    return differences


def verify_fingerprint(ledger_path: Path, workspace: Path, expected: dict) -> list[str]:
    return fingerprint_facets(fingerprint_differences(ledger_path, workspace, expected))


def fingerprint_facets(differences: list[dict]) -> list[str]:
    facets = []
    mapping = {"workspace": "workspace", "revision": "base_revision", "contract": "contract_sha256", "protected_input": "scope_sha256"}
    for item in differences:
        name = mapping[item["facet"]]
        if name not in facets:
            facets.append(name)
    return facets


def verifier_view(acceptance: dict) -> dict:
    verifier = acceptance["verifier"]
    if verifier["type"] == "human":
        return {"type": "human", "instructions": verifier["instructions"]}
    return {
        "type": "command",
        "argv": verifier["argv"],
        "cwd": verifier["cwd"],
        "timeout_seconds": verifier["timeout_seconds"],
        "expected_exit_code": verifier["expected_exit_code"],
    }


def find_acceptance(ledger: dict, acceptance_id: str) -> dict:
    matches = [item for item in ledger["acceptance"] if item["id"] == acceptance_id]
    if len(matches) != 1:
        raise ValueError(f"acceptance id must exist exactly once: {acceptance_id}")
    return matches[0]


def artifact_hashes(acceptance: dict, workspace: Path) -> dict[str, str | None]:
    return {
        display_path(workspace, path): file_hash(path)
        for path in (resolve_from(workspace, value) for value in acceptance["artifacts"])
    }


def bounded_tail(value: bytes | str | None, limit: int = 2000) -> str:
    if value is None:
        return ""
    text = value.decode(errors="replace") if isinstance(value, bytes) else value
    return text[-limit:]


def require_v4_mutation(legacy: dict | None, command: str) -> None:
    if legacy is not None:
        raise ValueError(f"{command} is read-only for schema v3; create a v4 ledger instead")


def run_acceptance(ledger_path: Path, acceptance_id: str, output: Path | None = None) -> tuple[bool, Path]:
    ledger_path = ledger_path.resolve()
    ledger, legacy, _ = load_ledger(ledger_path)
    require_v4_mutation(legacy, "run")
    acceptance = find_acceptance(ledger, acceptance_id)
    verifier = verifier_view(acceptance)
    if verifier["type"] != "command":
        raise ValueError(f"acceptance {acceptance_id} is not a command verifier")
    if ledger["authority"]["blocked"] or ledger["control"]["safety_stop"]:
        raise ValueError("authority or safety blocker prevents verifier execution")
    workspace = workspace_for(ledger, ledger_path.parent)
    stale = baseline_differences(ledger, workspace)
    if stale:
        reasons = ", ".join(f"{item['facet']}:{item['condition']}" for item in stale)
        raise StaleInputError(f"baseline is stale before verifier execution: {reasons}")
    cwd = resolve_from(workspace, verifier["cwd"])
    try:
        cwd.relative_to(workspace)
    except ValueError as error:
        raise ValueError("verifier.cwd must stay inside baseline.workspace") from error
    if not cwd.is_dir():
        raise ValueError(f"verifier.cwd does not exist: {cwd}")

    input_fingerprint = capture_fingerprint(ledger_path, workspace, protected_paths(ledger), False)
    started = datetime.now(timezone.utc)
    timed_out = False
    try:
        result = subprocess.run(verifier["argv"], cwd=cwd, capture_output=True, timeout=verifier["timeout_seconds"], check=False)
        exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out, exit_code, stdout, stderr = True, None, error.stdout, error.stderr
    finished = datetime.now(timezone.utc)
    artifacts = artifact_hashes(acceptance, workspace)
    passed = (
        not timed_out
        and exit_code == verifier["expected_exit_code"]
        and all(value is not None for value in artifacts.values())
        and all(value is not None for value in input_fingerprint["scope_sha256"].values())
    )
    evidence = {
        "schema_version": 3,
        "acceptance_id": acceptance_id,
        "contract_sha256": contract_digest(ledger),
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
        output = ledger_path.parent / "evidence" / f"{safe_id}-{finished.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    else:
        output = output.resolve()
    write_json(output, evidence)
    acceptance["evidence_files"].append(display_path(ledger_path.parent, output))
    acceptance["status"] = "passed" if passed else "failed"
    write_json(ledger_path, ledger)
    return passed, output


def hash_map_differences(expected: object, actual: dict, facet: str) -> list[dict]:
    if not isinstance(expected, dict):
        return [detail(facet, "invalid_evidence")]
    differences = []
    for path in sorted(set(expected) | set(actual)):
        expected_hash, actual_hash = expected.get(path), actual.get(path)
        if expected_hash is None:
            differences.append(detail(facet, "invalid_expected_hash", path=path, expected_sha256=None, actual_sha256=actual_hash))
        elif path not in actual or actual_hash is None:
            differences.append(detail(facet, "missing", path=path, expected_sha256=expected_hash, actual_sha256=actual_hash))
        elif expected_hash != actual_hash:
            differences.append(detail(facet, "changed", path=path, expected_sha256=expected_hash, actual_sha256=actual_hash))
    return differences


def command_acceptance_diagnostic(ledger: dict, legacy: dict | None, ledger_path: Path, acceptance: dict) -> dict:
    if acceptance["status"] != "passed":
        code = "verifier_failed" if acceptance["status"] == "failed" else "no_passed_evidence"
        return {"id": acceptance["id"], "verifier": "command", "state": "open", "reasons": [code], "stale": []}
    if not acceptance["evidence_files"]:
        return {"id": acceptance["id"], "verifier": "command", "state": "stale", "reasons": ["evidence_missing"], "stale": [detail("evidence", "missing")]}
    workspace = workspace_for(ledger, ledger_path.parent)
    expected_contract = contract_digest(ledger, legacy)
    expected_verifier = verifier_view(acceptance)
    current_artifacts = artifact_hashes(acceptance, workspace)
    latest = []
    for value in reversed(acceptance["evidence_files"]):
        try:
            evidence = read_json(resolve_from(ledger_path.parent, value))
        except (OSError, ValueError, json.JSONDecodeError):
            differences = [detail("evidence", "unreadable", path=value)]
        else:
            differences = []
            if evidence.get("acceptance_id") != acceptance["id"]:
                differences.append(detail("evidence", "wrong_acceptance"))
            if evidence.get("passed") is not True:
                differences.append(detail("evidence", "not_passed"))
            if evidence.get("contract_sha256") != expected_contract:
                differences.append(detail("contract", "changed", expected=evidence.get("contract_sha256"), actual=expected_contract))
            if evidence.get("verifier") != expected_verifier:
                differences.append(detail("verifier", "changed"))
            differences.extend(hash_map_differences(evidence.get("artifacts_sha256"), current_artifacts, "artifact"))
            fingerprint = evidence.get("input_fingerprint")
            if not isinstance(fingerprint, dict):
                differences.append(detail("evidence", "invalid_fingerprint"))
            else:
                try:
                    differences.extend(fingerprint_differences(ledger_path, workspace, fingerprint))
                except (OSError, ValueError, json.JSONDecodeError):
                    differences.append(detail("evidence", "invalid_fingerprint"))
        if not differences:
            return {"id": acceptance["id"], "verifier": "command", "state": "passed", "reasons": [], "stale": []}
        if not latest:
            latest = differences
    return {
        "id": acceptance["id"],
        "verifier": "command",
        "state": "stale",
        "reasons": sorted({f"{item['facet']}:{item['condition']}" for item in latest}),
        "stale": latest,
    }


def human_acceptance_diagnostic(ledger: dict, legacy: dict | None, ledger_path: Path, acceptance: dict) -> dict:
    attestation = acceptance["attestation"]
    if acceptance["status"] != "passed" or attestation["accepted"] is not True or not attestation["statement"]:
        return {"id": acceptance["id"], "verifier": "human", "state": "open", "reasons": ["human_attestation_required"], "stale": []}
    required = protected_paths(ledger) + acceptance["artifacts"]
    snapshot_value = attestation["fingerprint_snapshot"]
    if legacy is not None and not required and not snapshot_value:
        return {"id": acceptance["id"], "verifier": "human", "state": "passed", "reasons": ["legacy_unfingerprinted_attestation"], "stale": []}
    if not snapshot_value:
        return {"id": acceptance["id"], "verifier": "human", "state": "stale", "reasons": ["fingerprint_snapshot_missing"], "stale": [detail("evidence", "missing_fingerprint_snapshot")]}
    workspace = workspace_for(ledger, ledger_path.parent)
    try:
        snapshot = read_json(resolve_from(ledger_path.parent, snapshot_value))
        captured = snapshot.get("scope_sha256")
        if not isinstance(captured, dict):
            raise ValueError("invalid scope")
        expected_paths = {display_path(workspace, resolve_from(workspace, value)) for value in required}
        differences = [detail("protected_input", "not_captured", path=path) for path in sorted(expected_paths - set(captured))]
        differences.extend(fingerprint_differences(ledger_path, workspace, snapshot))
    except (OSError, ValueError, json.JSONDecodeError):
        differences = [detail("evidence", "invalid_fingerprint_snapshot", path=snapshot_value)]
    if differences:
        return {
            "id": acceptance["id"],
            "verifier": "human",
            "state": "stale",
            "reasons": sorted({f"{item['facet']}:{item['condition']}" for item in differences}),
            "stale": differences,
        }
    return {"id": acceptance["id"], "verifier": "human", "state": "passed", "reasons": [], "stale": []}


def acceptance_diagnostic(ledger: dict, legacy: dict | None, ledger_path: Path, acceptance: dict) -> dict:
    if acceptance["verifier"]["type"] == "command":
        return command_acceptance_diagnostic(ledger, legacy, ledger_path, acceptance)
    return human_acceptance_diagnostic(ledger, legacy, ledger_path, acceptance)


def is_open_critical(unknown: dict) -> bool:
    return unknown["impact"] == "critical" and (unknown["status"] == "open" or not unknown["evidence"])


def deadline_reached(value: object, now: datetime) -> bool:
    deadline = parse_deadline(value)
    return deadline is not None and now >= deadline


def baseline_differences(ledger: dict, workspace: Path) -> list[dict]:
    differences = []
    revision = ledger["baseline"]["revision"]
    if revision["mode"] == "exact":
        actual = git_head(workspace)
        if actual != revision["value"]:
            differences.append(detail("revision", "changed" if actual else "non_git", expected=revision["value"], actual=actual))
    for item in ledger["baseline"]["protected_inputs"]:
        if item["sha256"] is None:
            continue
        path = resolve_from(workspace, item["path"])
        try:
            actual = file_hash(path)
            condition = "missing" if actual is None else "changed"
        except ValueError:
            actual, condition = None, "not_file"
        if actual != item["sha256"]:
            differences.append(detail("protected_input", condition, path=item["path"], expected_sha256=item["sha256"], actual_sha256=actual))
    return differences


def unique_details(values: list[dict]) -> list[dict]:
    seen, result = set(), []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def next_action_for(state: str, acceptance: list[dict], critical: list[dict]) -> dict:
    if state == "STOP_SAFETY":
        return {"kind": "resolve_blocker", "message": "Resolve the authority or safety blocker before mutation."}
    if state == "STALE_INPUT":
        return {"kind": "refresh_and_verify", "message": "Refresh the listed stale inputs and rerun affected acceptance."}
    if state == "STOP_SUCCESS":
        return {"kind": "report_success", "message": "Report completion with current evidence."}
    if state == "WAITING_HUMAN":
        item = next(value for value in acceptance if value["state"] == "open")
        return {"kind": "request_human_attestation", "acceptance_id": item["id"]}
    if state == "STOP_BUDGET":
        return {"kind": "report_budget", "message": "Report the reached boundary and request an explicit extension."}
    if critical:
        return {"kind": "resolve_unknown", "unknown_id": critical[0]["id"], "safe_probe": critical[0]["safe_probe"]}
    item = next(value for value in acceptance if value["state"] != "passed")
    return {"kind": "run_verifier" if item["verifier"] == "command" else "request_human_attestation", "acceptance_id": item["id"]}


def stop_report_from(ledger: dict, legacy: dict | None, notes: list[str], ledger_path: Path, now: datetime | None = None) -> dict:
    workspace = workspace_for(ledger, ledger_path.parent)
    acceptance = [acceptance_diagnostic(ledger, legacy, ledger_path, item) for item in ledger["acceptance"]]
    critical = [
        {key: item[key] for key in ("id", "class", "statement", "status", "safe_probe")}
        for item in ledger["unknowns"]
        if is_open_critical(item)
    ]
    baseline_stale = baseline_differences(ledger, workspace)
    acceptance_stale = [entry for item in acceptance for entry in item["stale"]]
    authority_reasons = ledger["authority"]["reasons"] if ledger["authority"]["blocked"] else []
    safety_reasons = ledger["control"]["reasons"] if ledger["control"]["safety_stop"] else []
    if ledger["authority"]["blocked"] and not authority_reasons:
        authority_reasons = ["authority.blocked=true"]
    if ledger["control"]["safety_stop"] and not safety_reasons:
        safety_reasons = ["control.safety_stop=true"]

    states = [item["state"] for item in acceptance]
    current_time = now or datetime.now(timezone.utc)
    maximum = ledger["limits"]["max_iterations"]
    budget = (
        ledger["control"]["budget_exhausted"]
        or (isinstance(maximum, int) and ledger["progress"]["iteration"] >= maximum)
        or deadline_reached(ledger["limits"]["deadline"], current_time)
    )
    if authority_reasons or safety_reasons:
        state = "STOP_SAFETY"
    elif baseline_stale or "stale" in states:
        state = "STALE_INPUT"
    elif all(value == "passed" for value in states) and not critical:
        state = "STOP_SUCCESS"
    elif not critical and any(value == "open" for value in states) and all(
        item["state"] == "passed" or (item["state"] == "open" and item["verifier"] == "human") for item in acceptance
    ):
        state = "WAITING_HUMAN"
    elif budget:
        state = "STOP_BUDGET"
    else:
        state = "CONTINUE"

    stale = unique_details(baseline_stale + acceptance_stale)
    revision = ledger["baseline"]["revision"]
    report = {
        "schema_version": 1,
        "source_schema_version": 3 if legacy is not None else 4,
        "state": state,
        "exit_code": EXIT_CODES[state],
        "acceptance": {
            "passed": states.count("passed"),
            "total": len(states),
            "items": acceptance,
        },
        "stale": stale,
        "critical_unknowns": critical,
        "blockers": {"authority": authority_reasons, "safety": safety_reasons},
        "budget": {
            "iteration": ledger["progress"]["iteration"],
            "max_iterations": maximum,
            "deadline": ledger["limits"]["deadline"],
            "reached": budget,
        },
        "workspace": {
            "git": git_head(workspace) is not None,
            "dirty": git_dirty(workspace),
            "revision_mode": revision["mode"],
            "expected_revision": revision["value"],
            "actual_revision": git_head(workspace),
        },
        "normalization": notes,
        "next_action": next_action_for(state, acceptance, critical),
    }
    return report


def stop_report(ledger_path: Path, now: datetime | None = None) -> dict:
    ledger_path = ledger_path.resolve()
    ledger, legacy, notes = load_ledger(ledger_path)
    return stop_report_from(ledger, legacy, notes, ledger_path, now)


def stop_state(ledger: dict, ledger_path: Path, now: datetime | None = None) -> str:
    normalized, legacy, notes = normalize_ledger(ledger)
    return stop_report_from(normalized, legacy, notes, ledger_path.resolve(), now)["state"]


def advance_round(ledger_path: Path) -> tuple[int, int | None]:
    ledger_path = ledger_path.resolve()
    ledger, legacy, _ = load_ledger(ledger_path)
    require_v4_mutation(legacy, "round")
    ledger["progress"]["iteration"] += 1
    write_json(ledger_path, ledger)
    return ledger["progress"]["iteration"], ledger["limits"]["max_iterations"]


def base_test_ledger(root: Path, acceptance: dict | None = None) -> dict:
    if acceptance is None:
        acceptance = {
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
        }
    return {
        "schema_version": 4,
        "task_id": "test",
        "objective": "create verified output",
        "scope": {"in": [], "out": [], "interfaces": []},
        "baseline": {
            "workspace": str(root),
            "revision": {"mode": "none", "value": None},
            "environment": {},
            "protected_inputs": [],
            "rollback": "",
        },
        "authority": {"allowed_writes": [], "forbidden_actions": [], "requires_user_approval": [], "blocked": False, "reasons": []},
        "limits": {"max_iterations": 3, "deadline": None},
        "control": {"safety_stop": False, "budget_exhausted": False, "reasons": []},
        "progress": {"iteration": 0},
        "acceptance": [acceptance],
        "unknowns": [],
        "decisions": [],
        "handoff": {"current_focus": "", "changed_paths": [], "failed_attempts": [], "blockers": [], "next_action": ""},
    }


def legacy_test_ledger(root: Path, verifier: dict | None = None) -> dict:
    if verifier is None:
        verifier = {"type": "command", "argv": [sys.executable, "-c", "pass"], "cwd": ".", "timeout_seconds": 30, "expected_exit_code": 0}
    return {
        "schema_version": 3,
        "task_id": "legacy-test",
        "objective": "read legacy evidence",
        "scope": {"in": [], "out": [], "interfaces": []},
        "baseline": {"workspace": str(root), "revision": None, "environment": {}, "protected_inputs": [], "rollback": ""},
        "authority": {"allowed_writes": [], "forbidden_actions": [], "requires_user_approval": [], "blocked": False},
        "limits": {"max_iterations": 3, "deadline": None},
        "control": {"safety_stop": False, "budget_exhausted": False, "reasons": []},
        "progress": {"iteration": 0},
        "acceptance": [{"id": "AC-L", "criterion": "legacy passes", "verifier": verifier, "artifacts": [], "status": "passed", "evidence_files": ["legacy-evidence.json"]}],
        "unknowns": [],
        "decisions": [],
        "handoff": {"current_focus": "", "changed_paths": [], "failed_attempts": [], "blockers": [], "next_action": ""},
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        # 1. STOP_SUCCESS and 2. protected-input STALE_INPUT.
        case = root / "success"
        case.mkdir()
        ledger_path = case / "loop-ledger.json"
        ledger = base_test_ledger(case)
        write_json(ledger_path, ledger)
        assert run_acceptance(ledger_path, "AC-1")[0]
        assert stop_report(ledger_path)["state"] == "STOP_SUCCESS"
        rendered = json.dumps(stop_report(ledger_path), ensure_ascii=False, sort_keys=True)
        assert rendered == json.dumps(stop_report(ledger_path), ensure_ascii=False, sort_keys=True)
        source = case / "source.txt"
        source.write_text("before", encoding="utf-8")
        ledger = read_json(ledger_path)
        ledger["baseline"]["protected_inputs"] = [{"path": "source.txt", "sha256": file_hash(source)}]
        ledger["acceptance"][0].update({"status": "open", "evidence_files": [], "artifacts": []})
        ledger["acceptance"][0]["verifier"]["argv"] = [sys.executable, "-c", "pass"]
        write_json(ledger_path, ledger)
        assert run_acceptance(ledger_path, "AC-1")[0]
        source.write_text("after", encoding="utf-8")
        stale = stop_report(ledger_path)
        assert stale["state"] == "STALE_INPUT" and stale["stale"][0]["path"] == "source.txt"

        # 3. STOP_SAFETY, 4. STOP_BUDGET, and 5. CONTINUE.
        case = root / "states"
        case.mkdir()
        ledger_path = case / "loop-ledger.json"
        ledger = base_test_ledger(case)
        ledger["control"].update({"safety_stop": True, "reasons": ["unsafe"]})
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "STOP_SAFETY"
        try:
            run_acceptance(ledger_path, "AC-1")
        except ValueError:
            pass
        else:
            raise AssertionError("safety-blocked verifier executed")
        assert not (case / "result.txt").exists()
        ledger["control"] = {"safety_stop": False, "budget_exhausted": False, "reasons": []}
        ledger["progress"]["iteration"] = 0
        write_json(ledger_path, ledger)
        assert [advance_round(ledger_path)[0] for _ in range(3)] == [1, 2, 3]
        assert stop_report(ledger_path)["state"] == "STOP_BUDGET"
        ledger["progress"]["iteration"] = 2
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "CONTINUE"
        ledger["progress"]["iteration"] = 0
        ledger["limits"]["deadline"] = "2000-01-01T00:00:00Z"
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "STOP_BUDGET"

        # 6. Human-only work is WAITING_HUMAN even when the budget is reached.
        human = {
            "id": "AC-H",
            "criterion": "user reviews output",
            "verifier": {"type": "human", "instructions": "Review it"},
            "artifacts": [],
            "status": "open",
            "evidence_files": [],
            "attestation": {"accepted": False, "actor": "", "attested_at": None, "statement": "", "fingerprint_snapshot": None},
        }
        case = root / "human-wait"
        case.mkdir()
        ledger_path = case / "loop-ledger.json"
        ledger = base_test_ledger(case, human)
        ledger["progress"]["iteration"] = 3
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "WAITING_HUMAN"
        ledger["authority"].update({"blocked": True, "reasons": ["approval boundary"]})
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "STOP_SAFETY"
        ledger["authority"].update({"blocked": False, "reasons": []})
        wait_input = case / "input.txt"
        wait_input.write_text("current", encoding="utf-8")
        ledger["baseline"]["protected_inputs"] = [{"path": "input.txt", "sha256": "0" * 64}]
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "STALE_INPUT"
        ledger["baseline"]["protected_inputs"] = []

        # 7. A critical unknown prevents success and human waiting.
        ledger["unknowns"] = [{"id": "KU-1", "class": "KU", "statement": "Need proof", "impact": "critical", "status": "open", "safe_probe": "run probe", "evidence": []}]
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "STOP_BUDGET"
        ledger["progress"]["iteration"] = 0
        write_json(ledger_path, ledger)
        report = stop_report(ledger_path)
        assert report["state"] == "CONTINUE" and report["critical_unknowns"][0]["id"] == "KU-1"

        # 8. Exact revision rejects a different or non-Git HEAD.
        case = root / "revision"
        case.mkdir()
        subprocess.run(["git", "init", "-q", str(case)], check=True)
        subprocess.run(["git", "-C", str(case), "config", "user.email", "self@test.invalid"], check=True)
        subprocess.run(["git", "-C", str(case), "config", "user.name", "loopctl self-test"], check=True)
        (case / "tracked.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", str(case), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(case), "commit", "-qm", "fixture"], check=True)
        ledger_path = case / "loop-ledger.json"
        ledger = base_test_ledger(case)
        ledger["baseline"]["revision"] = {"mode": "exact", "value": "0" * 40}
        sentinel = case / "revision-verifier-ran.txt"
        ledger["acceptance"][0]["verifier"]["argv"] = [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('revision-verifier-ran.txt').write_text('bad')",
        ]
        write_json(ledger_path, ledger)
        assert stop_report(ledger_path)["state"] == "STALE_INPUT"
        try:
            run_acceptance(ledger_path, "AC-1")
        except ValueError:
            pass
        else:
            raise AssertionError("revision-stale verifier executed")
        assert not sentinel.exists()
        ledger["baseline"]["revision"] = {"mode": "exact", "value": git_head(case)}
        ledger["baseline"]["protected_inputs"] = [{"path": "tracked.txt", "sha256": "0" * 64}]
        write_json(ledger_path, ledger)
        try:
            run_acceptance(ledger_path, "AC-1")
        except ValueError:
            pass
        else:
            raise AssertionError("protected-input-stale verifier executed")
        assert not sentinel.exists()

        # 9. Malformed path/hash and 12. unknown v4 key/enum are rejected.
        ledger = base_test_ledger(case)
        ledger["baseline"]["protected_inputs"] = [{"path": "tracked.txt", "sha256": "bad"}]
        try:
            validate_ledger(ledger)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed sha256 accepted")
        malformed_legacy = legacy_test_ledger(case)
        malformed_legacy["baseline"]["protected_inputs"] = ["tracked.txt (SHA256 bad)"]
        try:
            normalize_ledger(malformed_legacy)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed legacy path/hash accepted")
        ledger = base_test_ledger(case)
        ledger["extra"] = True
        try:
            validate_ledger(ledger)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown v4 key accepted")
        ledger = base_test_ledger(case)
        ledger["acceptance"][0]["verifier"]["extra"] = True
        try:
            validate_ledger(ledger)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown nested v4 key accepted")
        ledger = base_test_ledger(case)
        ledger["unknowns"] = [{"id": "X", "class": "MAYBE", "statement": "x", "impact": "critical", "status": "open", "safe_probe": "x", "evidence": []}]
        try:
            validate_ledger(ledger)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown v4 enum accepted")
        ledger = base_test_ledger(case)
        ledger["decisions"] = [
            {"id": "D-1", "statement": "one", "rationale": "", "evidence": []},
            {"id": "D-1", "statement": "two", "rationale": "", "evidence": []},
        ]
        try:
            validate_ledger(ledger)
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate decision id accepted")

        # 10. Mixed legacy aliases and 11. v3 evidence normalize read-only.
        case = root / "legacy"
        case.mkdir()
        sentinel = case / "should-not-run.txt"
        verifier = {
            "type": "command",
            "argv": [sys.executable, "-c", "from pathlib import Path; Path('should-not-run.txt').write_text('bad')"],
            "cwd": ".",
            "timeout_seconds": 30,
            "expected_exit_code": 0,
        }
        ledger_path = case / "loop-ledger.json"
        legacy = legacy_test_ledger(case, verifier)
        legacy["unknowns"] = [
            {"id": "KU-1", "class": "KU", "statement": "one", "impact": "critical", "status": "open", "safe_probe": "probe", "user_accepted": False, "evidence": []},
            {"id": "UK-1", "type": "UK", "q": "two", "impact": "medium", "status": "open", "probe": "probe", "evidence": []},
        ]
        write_json(ledger_path, legacy)
        normalized, original, _ = load_ledger(ledger_path)
        assert original is not None and [item["class"] for item in normalized["unknowns"]] == ["KU", "UK"]
        defaulted = legacy_test_ledger(case, {"type": "command", "argv": [sys.executable, "-c", "pass"]})
        normalized, _, _ = normalize_ledger(defaulted)
        assert verifier_view(normalized["acceptance"][0]) == {
            "type": "command",
            "argv": [sys.executable, "-c", "pass"],
            "cwd": ".",
            "timeout_seconds": 300,
            "expected_exit_code": 0,
        }
        fingerprint = capture_fingerprint(ledger_path, case, [], False)
        evidence = {
            "schema_version": 2,
            "acceptance_id": "AC-L",
            "contract_sha256": digest(legacy_contract_view(legacy)),
            "input_fingerprint": fingerprint,
            "verifier": verifier,
            "artifacts_sha256": {},
            "passed": True,
        }
        write_json(case / "legacy-evidence.json", evidence)
        before = ledger_path.read_bytes()
        assert stop_report(ledger_path)["state"] == "CONTINUE"  # critical KU remains open
        legacy["unknowns"] = []
        write_json(ledger_path, legacy)
        evidence["contract_sha256"] = digest(legacy_contract_view(legacy))
        evidence["input_fingerprint"] = capture_fingerprint(ledger_path, case, [], False)
        write_json(case / "legacy-evidence.json", evidence)
        before = ledger_path.read_bytes()
        assert stop_report(ledger_path)["state"] == "STOP_SUCCESS" and ledger_path.read_bytes() == before
        try:
            run_acceptance(ledger_path, "AC-L")
        except ValueError:
            pass
        else:
            raise AssertionError("schema v3 run was not rejected")
        try:
            advance_round(ledger_path)
        except ValueError:
            pass
        else:
            raise AssertionError("schema v3 round was not rejected")
        assert not sentinel.exists() and ledger_path.read_bytes() == before
        legacy["unknowns"] = [
            {"id": "R-1", "class": "KU", "statement": "risk", "impact": "critical", "status": "accepted-risk", "safe_probe": "", "user_accepted": True, "evidence": []}
        ]
        write_json(ledger_path, legacy)
        assert stop_report(ledger_path)["state"] == "STOP_SUCCESS"
        legacy["unknowns"][0].update({"user_accepted": False, "evidence": ["legacy note"]})
        write_json(ledger_path, legacy)
        assert stop_report(ledger_path)["state"] == "CONTINUE"
        conflict = copy.deepcopy(legacy)
        conflict["unknowns"] = [{"id": "X", "class": "KU", "type": "UK", "statement": "x", "q": "x", "impact": "critical", "status": "open", "safe_probe": "x", "probe": "x", "evidence": []}]
        try:
            normalize_ledger(conflict)
        except ValueError:
            pass
        else:
            raise AssertionError("conflicting legacy aliases accepted")

        # 13. Human evidence becomes stale after reviewed artifact changes.
        case = root / "human-stale"
        case.mkdir()
        reviewed = case / "reviewed.txt"
        protected = case / "protected.txt"
        reviewed.write_text("approved", encoding="utf-8")
        protected.write_text("input", encoding="utf-8")
        human = copy.deepcopy(human)
        human.update({
            "artifacts": ["reviewed.txt"],
            "status": "passed",
            "attestation": {
                "accepted": True,
                "actor": "reviewer-label",
                "attested_at": "2026-08-26T00:00:00Z",
                "statement": "Reviewed artifact approved",
                "fingerprint_snapshot": "human-fingerprint.json",
            },
        })
        ledger_path = case / "loop-ledger.json"
        ledger = base_test_ledger(case, human)
        ledger["baseline"]["protected_inputs"] = [{"path": "protected.txt", "sha256": file_hash(protected)}]
        write_json(ledger_path, ledger)
        write_json(case / "human-fingerprint.json", capture_fingerprint(ledger_path, case, ["protected.txt", "reviewed.txt"], False))
        assert stop_report(ledger_path)["state"] == "STOP_SUCCESS"
        reviewed.write_text("changed", encoding="utf-8")
        assert stop_report(ledger_path)["state"] == "STALE_INPUT"
        reviewed.write_text("approved", encoding="utf-8")
        protected.write_text("changed", encoding="utf-8")
        assert stop_report(ledger_path)["state"] == "STALE_INPUT"

        # 14. argv stays an argv array; shell metacharacters remain literal.
        case = root / "argv"
        case.mkdir()
        literal = "literal;touch should-not-exist"
        acceptance = {
            "id": "AC-A",
            "criterion": "argument remains literal",
            "verifier": {
                "type": "command",
                "argv": [sys.executable, "-c", "from pathlib import Path; import sys; Path('argv.txt').write_text(sys.argv[1])", literal],
                "cwd": ".",
                "timeout_seconds": 30,
                "expected_exit_code": 0,
            },
            "artifacts": ["argv.txt"],
            "status": "open",
            "evidence_files": [],
        }
        ledger_path = case / "loop-ledger.json"
        write_json(ledger_path, base_test_ledger(case, acceptance))
        assert run_acceptance(ledger_path, "AC-A")[0]
        assert (case / "argv.txt").read_text(encoding="utf-8") == literal
        assert not (case / "should-not-exist").exists()

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
    verify.add_argument("--json", action="store_true")

    run = commands.add_parser("run")
    run.add_argument("ledger")
    run.add_argument("--acceptance", required=True)
    run.add_argument("--output")

    round_command = commands.add_parser("round")
    round_command.add_argument("ledger")

    stop = commands.add_parser("stop")
    stop.add_argument("ledger")
    stop.add_argument("--json", action="store_true")
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
            ledger_path = Path(args.ledger).resolve()
            differences = fingerprint_differences(ledger_path, Path(args.workspace).resolve(), read_json(Path(args.snapshot)))
            if args.json:
                print(json.dumps({"state": "STALE_INPUT" if differences else "MATCH", "exit_code": EXIT_CODES["STALE_INPUT"] if differences else 0, "differences": differences}, ensure_ascii=False, indent=2))
            else:
                mismatches = fingerprint_facets(differences)
                print("STALE_INPUT " + ",".join(mismatches) if mismatches else "MATCH")
            return EXIT_CODES["STALE_INPUT"] if differences else 0
        if args.command == "run":
            passed, output = run_acceptance(Path(args.ledger), args.acceptance, Path(args.output) if args.output else None)
            print(f"{'VERIFY_PASS' if passed else 'VERIFY_FAIL'} {args.acceptance} {output}")
            return 0 if passed else 4
        if args.command == "round":
            iteration, maximum = advance_round(Path(args.ledger))
            print(f"ROUND {iteration}/{maximum if maximum is not None else '-'}")
            return 0
        if args.command == "stop":
            report = stop_report(Path(args.ledger))
            print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else report["state"])
            return report["exit_code"]
        parser.print_help()
        return 2
    except StaleInputError as error:
        print(f"STALE_INPUT {error}", file=sys.stderr)
        return EXIT_CODES["STALE_INPUT"]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"INVALID_INPUT {error}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
