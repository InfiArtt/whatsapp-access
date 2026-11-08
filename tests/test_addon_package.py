import ast
import re
import zipfile

from conftest import ROOT

import build_addon

ADDON_DIR = ROOT / "addon"
INDONESIAN_PO = ADDON_DIR / "locale" / "id" / "LC_MESSAGES" / "nvda.po"


def translatable_strings() -> set[str]:
    """Every string literal passed to _() in the add-on's code."""
    found = set()
    for path in ADDON_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_":
                assert isinstance(node.args[0], ast.Constant), (
                    f"Non-literal _() argument in {path}:{node.lineno}"
                )
                found.add(node.args[0].value)
    return found


def test_every_translatable_string_has_an_indonesian_translation():
    catalog = build_addon.parse_po(INDONESIAN_PO)
    missing = translatable_strings() - set(catalog)
    assert not missing, f"Add these to {INDONESIAN_PO.name}: {missing}"
    assert all(catalog[msgid] for msgid in translatable_strings())


def test_translations_keep_format_placeholders():
    for msgid, msgstr in build_addon.parse_po(INDONESIAN_PO).items():
        assert set(re.findall(r"\{\w+\}", msgid)) == set(re.findall(r"\{\w+\}", msgstr)), msgid


def test_translations_keep_one_accelerator():
    for msgid, msgstr in build_addon.parse_po(INDONESIAN_PO).items():
        assert msgid.count("&") == msgstr.count("&"), msgid


def test_package_contains_plugin_bridge_manifest_and_translations():
    output = build_addon.build()
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert {
        "manifest.ini",
        "installTasks.py",
        "globalPlugins/whatsAppAccess/__init__.py",
        "globalPlugins/whatsAppAccess/pageBridge.js",
        "sounds/sent.wav",
        "sounds/received.wav",
        "sounds/recordStart.wav",
        "sounds/recordStop.wav",
        "sounds/pause.wav",
        "sounds/discard.wav",
        "sounds/ring.wav",
        "sounds/notifyBell.wav",
        "sounds/notifyKalimba.wav",
        "sounds/notifyFlute.wav",
        "sounds/tick.wav",
        "sounds/micOff.wav",
        "sounds/micOn.wav",
        "sounds/callJoin.wav",
        "sounds/callLeave.wav",
        "sounds/callHand.wav",
        "sounds/callReaction.wav",
        "locale/id/LC_MESSAGES/nvda.mo",
        "locale/id/manifest.ini",
        "doc/en/readme.html",
        "doc/id/readme.html",
        "COPYING.txt",
    } <= names
    assert not any(name.endswith((".po", ".pyc")) for name in names)
