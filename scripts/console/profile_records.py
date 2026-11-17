"""Count the tagged headings in the checked-in profile records."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def count_entries(filename, marker):
    heading = re.compile(rf"^ {{0,3}}##[ \t]+\S.*?[ \t]+<!--[ \t]*{re.escape(marker)}[ \t]*-->[ \t]*$")
    fence = None
    count = 0
    for line in (ROOT / filename).read_text(encoding="utf-8").splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            run, rest = match.groups()
            if fence is None:
                fence = run
            elif run.startswith(fence) and not rest.strip():
                fence = None
        elif fence is None and heading.fullmatch(line):
            count += 1
    return count
