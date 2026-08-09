import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def test_dogwood_py_replay_cli_example_matches_expected_output():
    command = [
        sys.executable,
        "-m",
        "dogwood.cli",
        "replay",
        str(ROOT / "examples/cli/policy.dw"),
        "--policy-schema",
        str(ROOT / "examples/cli/schema.cedarschema"),
        "--trace",
        str(ROOT / "examples/cli/trace.log"),
    ]

    completed = subprocess.run(command, cwd=ROOT, env=CLI_ENV, text=True, capture_output=True, check=True)
    expected = (ROOT / "examples/cli/expected.out").read_text().strip()
    assert completed.stdout.strip() == expected
    assert completed.stderr == ""


def test_dogwood_py_replay_accepts_event_schema():
    command = [
        sys.executable,
        "-m",
        "dogwood.cli",
        "replay",
        str(ROOT / "examples/cli/policy.dw"),
        "--policy-schema",
        str(ROOT / "examples/cli/schema.cedarschema"),
        "--event-schema",
        str(ROOT / "examples/fastapi_simple/event.dwschema"),
        "--trace",
        str(ROOT / "examples/cli/trace.log"),
    ]

    completed = subprocess.run(command, cwd=ROOT, env=CLI_ENV, text=True, capture_output=True, check=True)
    expected = (ROOT / "examples/cli/expected.out").read_text().strip()
    assert completed.stdout.strip() == expected
    assert completed.stderr == ""
