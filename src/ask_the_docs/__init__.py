"""ask-the-docs: section-level search over codebases' Markdown docs."""

from importlib.metadata import version

__version__ = version("ask-the-docs")


def main() -> None:
    """Print the version. Placeholder entry point until the CLI lands in #3."""
    print(f"atd {__version__}")
