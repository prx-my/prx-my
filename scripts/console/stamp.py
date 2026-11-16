"""Version every README image link by its content so browsers fetch an update as soon as it lands.

GitHub serves README images with a five-minute browser cache and the same URL after every change.
A `?v=<hash>` suffix gives changed files a new URL; unchanged files keep theirs and stay cached.
Run after every generator, since some of them rewrite README image links.
"""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
LINK = re.compile(
    r'((?:src|srcset)=")'
    r"((?:https://raw\.githubusercontent\.com/prx-my/prx-my/main/)?((?:profile-assets|assets)/[^\"?]+))"
    r'(?:\?v=[0-9a-f]+)?"'
)


def stamp(text):
    def version(match):
        path = ROOT / match[3]
        if not path.is_file():
            raise FileNotFoundError(f"README links to a missing image: {match[3]}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
        return f'{match[1]}{match[2]}?v={digest}"'

    return LINK.sub(version, text)


def main():
    text = README.read_text(encoding="utf-8")
    stamped = stamp(text)
    assert stamp(stamped) == stamped, "stamping must be idempotent"
    README.write_text(stamped, encoding="utf-8")


if __name__ == "__main__":
    main()
