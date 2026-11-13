"""Prepare the next patch version. Preview is the default; use --write after review."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the reviewed changes")
    args = parser.parse_args()
    package = ROOT / "ec_mcp" / "__init__.py"
    project = ROOT / "pyproject.toml"
    text = package.read_text(encoding="utf-8")
    match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', text)
    if not match:
        raise SystemExit("Cannot locate package version")
    old = match.group(0).split('"')[1]
    new = ".".join([match.group(1), match.group(2), str(int(match.group(3)) + 1)])
    metadata = project.read_text(encoding="utf-8")
    if f'version = "{old}"' not in metadata:
        raise SystemExit("Package and project versions differ; repair before bumping")
    changes = {
        package: text.replace(f'__version__ = "{old}"', f'__version__ = "{new}"'),
        project: metadata.replace(f'version = "{old}"', f'version = "{new}"', 1),
    }
    for path in (ROOT.parent / "README.md", ROOT / "README.md", ROOT / "QA-BATTERY.md", ROOT / "QA-FULL.md"):
        content = path.read_text(encoding="utf-8")
        updated = content.replace(old, new)
        if updated != content:
            changes[path] = updated
    print(f"{old} -> {new}")
    for path in changes:
        print(path.relative_to(ROOT.parent))
    if args.write:
        for path, content in changes.items():
            path.write_text(content, encoding="utf-8")
        print("Written. Review the diff and run CI before tagging a release.")
    else:
        print("Preview only. Review these files before rerunning with --write.")


if __name__ == "__main__":
    main()
