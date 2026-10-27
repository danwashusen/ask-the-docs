"""List a codebase's Markdown files, per docs/architecture/indexing.md §File discovery."""

import os
import subprocess
from pathlib import Path, PurePosixPath

from ask_the_docs.config import CodebaseConfig


def discover(codebase: CodebaseConfig) -> list[str]:
    """Return the codebase's ``*.md`` paths, relative to its root, sorted and POSIX-style.

    Inside a git repo, git lists tracked and untracked files and honours every
    ``.gitignore``. Outside git, or when git is not installed, the docs folders
    are walked. Exclude globs apply either way.
    """
    root = codebase.root
    paths = _git_list(root, codebase.docs)
    if paths is None:
        paths = _walk(root, codebase.docs)
    return sorted(
        path
        for path in set(paths)
        if path.endswith(".md")
        and not any(PurePosixPath(path).full_match(glob) for glob in codebase.exclude)
    )


def _git_list(root: Path, docs: list[str]) -> list[str] | None:
    """List files under ``docs`` with git, or return None when git cannot be used."""
    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None
    listing = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-co",
            "--exclude-standard",
            "-z",
            "--",
            *docs,
        ],
        capture_output=True,
        check=True,
        # Docs entries are folders, not git pathspecs: no globs or `:` magic.
        env={**os.environ, "GIT_LITERAL_PATHSPECS": "1"},
    )
    names = listing.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    # A tracked file deleted from disk is still listed until the deletion is staged.
    return [name for name in names if name and (root / name).is_file()]


def _walk(root: Path, docs: list[str]) -> list[str]:
    """List every file under the ``docs`` folders by walking the file system."""
    found: list[str] = []
    for folder in docs:
        base = root / folder
        if base.is_file():
            found.append(base.relative_to(root).as_posix())
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for filename in filenames:
                found.append((Path(dirpath) / filename).relative_to(root).as_posix())
    return found
