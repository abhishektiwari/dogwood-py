#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


SUSPICIOUS = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\ufeff": "BYTE ORDER MARK",
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202c": "POP DIRECTIONAL FORMATTING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
}


def main(argv: list[str]) -> int:
    failed = False
    for raw in argv:
        path = Path(raw)
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            for char, name in SUSPICIOUS.items():
                if char in line:
                    print(f"{path}:{line_no}: hidden unicode character: {name}")
                    failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
