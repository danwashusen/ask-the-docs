import shutil
import subprocess
from pathlib import Path

import pytest

from ask_the_docs.codebase import discover
from ask_the_docs.config import CodebaseConfig

needs_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not installed"
)

EXPECTED = ["docs/guide.md", "docs/notes/untracked.md", "docs/ref/api.md"]


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch):
    """Keep the developer's git config (signing, hooks, global ignores) out of the tests."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def make_tree(root: Path) -> None:
    files = {
        "docs/guide.md": "# Guide\n",
        "docs/ref/api.md": "# API\n",
        "docs/notes/untracked.md": "# Notes\n",
        "docs/archive/old/2019.md": "# Old\n",
        "docs/image.png": "not markdown",
        "docs/build/generated.md": "# Generated\n",
        "README.md": "# Outside the docs folder\n",
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def codebase(root: Path) -> CodebaseConfig:
    return CodebaseConfig(name="sample", root=root, exclude=["docs/archive/**"])


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@needs_git
def test_git_listing(tmp_path):
    make_tree(tmp_path)
    (tmp_path / "docs" / "gone.md").write_text("# Gone\n")
    (tmp_path / ".gitignore").write_text("docs/build/\n")
    git(tmp_path, "init", "-q")
    git(
        tmp_path,
        "add",
        "docs/guide.md",
        "docs/ref/api.md",
        "docs/gone.md",
        ".gitignore",
    )
    git(tmp_path, "commit", "-q", "-m", "init")
    (tmp_path / "docs" / "gone.md").unlink()

    assert discover(codebase(tmp_path)) == EXPECTED


@needs_git
def test_git_listing_from_a_subfolder_root(tmp_path):
    root = tmp_path / "service"
    make_tree(root)
    git(tmp_path, "init", "-q")

    assert discover(codebase(root)) == sorted(EXPECTED + ["docs/build/generated.md"])


def test_walk_outside_git(tmp_path):
    make_tree(tmp_path)

    assert discover(codebase(tmp_path)) == sorted(
        EXPECTED + ["docs/build/generated.md"]
    )


def test_walk_when_git_is_missing(tmp_path, monkeypatch):
    make_tree(tmp_path)
    if shutil.which("git"):
        git(tmp_path, "init", "-q")
        (tmp_path / ".gitignore").write_text("docs/build/\n")
    monkeypatch.setenv("PATH", "")

    # The walk ignores .gitignore, so the ignored file reappears.
    assert discover(codebase(tmp_path)) == sorted(
        EXPECTED + ["docs/build/generated.md"]
    )


def test_several_docs_folders_and_missing_folder(tmp_path):
    make_tree(tmp_path)
    (tmp_path / "adr").mkdir()
    (tmp_path / "adr" / "0001.md").write_text("# ADR\n")
    config = CodebaseConfig(
        name="s", root=tmp_path, docs=["adr/", "missing/"], exclude=[]
    )

    assert discover(config) == ["adr/0001.md"]
