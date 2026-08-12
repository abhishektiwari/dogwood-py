from __future__ import annotations

from pathlib import Path

from dogwood.cli import main


def run() -> int:
    example_dir = Path(__file__).resolve().parent
    return main(
        [
            "replay",
            str(example_dir / "policy.dw"),
            "--policy-schema",
            str(example_dir / "schema.cedarschema"),
            "--trace",
            str(example_dir / "trace.log"),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(run())
