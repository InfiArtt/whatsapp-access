"""Every string translators see has a "Translators:" comment right above it, as NVDA's coding standards ask.

The comment must be on the lines just before the line with _( or just before the string itself, with
nothing in between, so translation tools attach it to that string.
"""

import io
import tokenize
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parent.parent / "addon"
GETTEXT = {"_", "pgettext", "ngettext", "npgettext"}


def comment_above(lines: list[str], line: int) -> bool:
    """Whether the lines just above line (1-based) are a comment block with "Translators:" in it."""
    index = line - 2
    block = []
    while index >= 0 and lines[index].strip().startswith("#"):
        block.append(lines[index])
        index -= 1
    return any("Translators:" in comment for comment in block)


def missing_comments(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type != tokenize.NL]
    missing = []
    for index, token in enumerate(tokens[:-2]):
        if token.type != tokenize.NAME or token.string not in GETTEXT:
            continue
        if tokens[index + 1].string != "(" or (index and tokens[index - 1].string in (".", "def")):
            continue
        string = next(
            (t for t in tokens[index + 2 :] if t.type in (tokenize.STRING, tokenize.FSTRING_START)), None
        )
        if string is None or string.type != tokenize.STRING:
            # _() of a variable: the string it holds has its comment where it is written.
            continue
        if not (comment_above(lines, token.start[0]) or comment_above(lines, string.start[0])):
            missing.append(f"{path.relative_to(PACKAGE)}:{token.start[0]}: {string.string[:60]}")
    return missing


@pytest.mark.parametrize("path", sorted(PACKAGE.rglob("*.py")), ids=lambda p: p.name)
def test_every_translatable_string_has_a_translators_comment(path):
    assert missing_comments(path) == []
