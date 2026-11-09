"""A method defined twice in a class silently replaces the first: Enter on a playing voice message once
called the voice note recorder's pause, with the wrong arguments."""

import ast

import pytest
from conftest import PACKAGE_DIR

MODULES = sorted(PACKAGE_DIR.glob("*.py"))


@pytest.mark.parametrize("path", MODULES, ids=lambda path: path.name)
def test_no_method_is_defined_twice_in_a_class(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    twice = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            seen = set()
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    if item.name in seen and not item.decorator_list:
                        twice.append(f"{node.name}.{item.name}")
                    seen.add(item.name)
    assert twice == []


@pytest.mark.parametrize("path", MODULES, ids=lambda path: path.name)
def test_no_wx_timer_owned_by_a_window(path):
    # A wx.Timer whose owner is destroyed while it runs, as when plugins are reloaded during playback,
    # crashed NVDA. wx.CallLater, checking the window is still there, is used instead.
    assert "wx.Timer(" not in path.read_text(encoding="utf-8")
