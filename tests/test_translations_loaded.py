import re

from conftest import PACKAGE_DIR

CALL = re.compile(r"^\s*addonHandler\.initTranslation\(\)", re.MULTILINE)


def test_every_module_with_translatable_strings_loads_the_add_on_translations():
    # NVDA puts the add-on's _() only in the module that calls initTranslation(); any other module
    # gets NVDA's own _(), and its strings stay in English for Indonesian users.
    missing = [
        path.name
        for path in sorted(PACKAGE_DIR.glob("*.py"))
        if re.search(r"\b_\(", path.read_text(encoding="utf-8"))
        and not CALL.search(path.read_text(encoding="utf-8"))
    ]
    assert missing == []
