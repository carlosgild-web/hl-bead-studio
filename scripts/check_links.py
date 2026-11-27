"""Check the relative links and images in the README and the docs: `python scripts/check_links.py`.

Every `](target)` and `src="target"` that is not a URL must resolve to a file or folder in the
repo, and every `#anchor` must match a heading of the file it points to (GitHub's slugs). Exit
code 1 lists what is broken. Used for the README standard's checklist (phase 10).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), ROOT / "video" / "README.md"]
FILES += sorted((ROOT / "docs").glob("*/README.md"))

LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|src=\"([^\"]+)\"")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    return {slug(m) for m in re.findall(r"^#{1,6}\s+(.+)$", body, re.M)}


def broken(path: Path) -> list[str]:
    body = COMMENT.sub("", FENCE.sub("", path.read_text(encoding="utf-8")))
    problems = []
    for match in LINK.finditer(body):
        target = match.group(1) or match.group(2)
        if re.match(r"^[a-z]+:", target):
            continue
        file_part, _, anchor = target.partition("#")
        dest = (path.parent / file_part).resolve() if file_part else path
        if not dest.exists():
            problems.append(f"{target} (no such file)")
        elif anchor and dest.suffix == ".md" and anchor not in anchors(dest):
            problems.append(f"{target} (no heading #{anchor})")
    return problems


def main() -> int:
    failed = 0
    for path in FILES:
        if not path.exists():
            continue
        for problem in broken(path):
            print(f"{path.relative_to(ROOT).as_posix()}: {problem}")
            failed += 1
    print(f"{len(FILES)} files checked, {failed} broken links")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
