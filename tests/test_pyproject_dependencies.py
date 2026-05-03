"""Smoke test: confirm PyQt6 is declared as a dependency."""

from pathlib import Path
import re


def test_pyqt6_is_declared_in_pyproject():
    """PyQt6 must appear in pyproject.toml dependencies.

    The analyzer GUI requires PyQt6 at runtime. Without this
    declaration, fresh clones running `pip install -e .` get a
    broken analyzer.
    """
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text()

    match = re.search(
        r'^\s*"PyQt6\b[^"]*"',
        content,
        re.MULTILINE | re.IGNORECASE,
    )
    assert match is not None, (
        "PyQt6 must be declared in pyproject.toml [project] dependencies. "
        "Without it, fresh clones cannot run the analyzer GUI."
    )
