import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("loopctl", ROOT / "scripts" / "loopctl.py")
LOOPCTL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOOPCTL)
SCRIPT = ROOT / "scripts" / "loopctl.py"


class LoopctlV4Test(unittest.TestCase):
    def test_template_and_regressions(self):
        LOOPCTL.validate_ledger(json.loads((ROOT / "assets" / "loop-ledger.template.json").read_text(encoding="utf-8")))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            LOOPCTL.self_test()
        self.assertEqual(output.getvalue().strip(), "SELF_TEST_OK")

    def test_cli_states_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger_path = root / "loop-ledger.json"

            def write(ledger):
                LOOPCTL.write_json(ledger_path, ledger)

            def cli(*args):
                return subprocess.run(
                    [sys.executable, str(SCRIPT), *map(str, args)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )

            ledger = LOOPCTL.base_test_ledger(root)
            write(ledger)
            result = cli("run", ledger_path, "--acceptance", "AC-1")
            self.assertEqual((result.returncode, result.stdout.split()[0]), (0, "VERIFY_PASS"))
            result = cli("stop", ledger_path)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, "STOP_SUCCESS"))

            ledger = LOOPCTL.base_test_ledger(root)
            write(ledger)
            result = cli("stop", ledger_path)
            self.assertEqual((result.returncode, result.stdout.strip()), (10, "CONTINUE"))

            human = {
                "id": "AC-H",
                "criterion": "review",
                "verifier": {"type": "human", "instructions": "review"},
                "artifacts": [],
                "status": "open",
                "evidence_files": [],
                "attestation": {"accepted": False, "actor": "", "attested_at": None, "statement": "", "fingerprint_snapshot": None},
            }
            ledger = LOOPCTL.base_test_ledger(root, human)
            write(ledger)
            result = cli("stop", ledger_path, "--json")
            report = json.loads(result.stdout)
            self.assertEqual((result.returncode, report["state"], report["exit_code"]), (20, "WAITING_HUMAN", 20))

            ledger = LOOPCTL.base_test_ledger(root)
            ledger["progress"]["iteration"] = 3
            write(ledger)
            result = cli("stop", ledger_path)
            self.assertEqual((result.returncode, result.stdout.strip()), (31, "STOP_BUDGET"))

            ledger = LOOPCTL.base_test_ledger(root)
            (root / "input.txt").write_text("current", encoding="utf-8")
            ledger["baseline"]["protected_inputs"] = [{"path": "input.txt", "sha256": "0" * 64}]
            write(ledger)
            result = cli("stop", ledger_path)
            self.assertEqual((result.returncode, result.stdout.strip()), (33, "STALE_INPUT"))
            result = cli("run", ledger_path, "--acceptance", "AC-1")
            self.assertEqual(result.returncode, 33)
            self.assertTrue(result.stderr.startswith("STALE_INPUT "))

            ledger = LOOPCTL.base_test_ledger(root)
            ledger["authority"].update({"blocked": True, "reasons": ["approval required"]})
            write(ledger)
            result = cli("stop", ledger_path)
            self.assertEqual((result.returncode, result.stdout.strip()), (40, "STOP_SAFETY"))

            ledger["extra"] = True
            write(ledger)
            result = cli("stop", ledger_path)
            self.assertEqual(result.returncode, 64)
            self.assertTrue(result.stderr.startswith("INVALID_INPUT "))


if __name__ == "__main__":
    unittest.main()
