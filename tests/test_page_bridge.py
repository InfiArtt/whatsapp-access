"""Pure helpers in pageBridge.js, run with Node when it is installed (it is on GitHub's Windows runners)."""

import json
import shutil
import subprocess

import pytest
from conftest import PACKAGE_DIR

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")

RUN_HELPER = """
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("\\tfunction replaceMentions");
const end = source.indexOf("\\tasync function sendText");
const replaceMentions = new Function(source.slice(start, end) + "; return replaceMentions;")();
const [text, mentions] = JSON.parse(process.argv[2]);
const result = replaceMentions(text, mentions);
process.stdout.write(JSON.stringify({ text: result.text, used: [...result.used].sort() }));
"""

MENTIONS = [
    {"name": "An", "number": "111"},
    {"name": "Andi", "number": "222"},
    {"name": "Dr. (Budi)", "number": "333"},
]


def mention(text: str) -> dict:
    result = subprocess.run(
        [NODE, "-e", RUN_HELPER, str(PACKAGE_DIR / "pageBridge.js"), json.dumps([text, MENTIONS])],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("written", "sent", "used"),
    [
        ("@Andi halo", "@222 halo", ["Andi"]),
        ("@An dan @Andi", "@111 dan @222", ["An", "Andi"]),
        ("@An, ok", "@111, ok", ["An"]),
        ("hai @Dr. (Budi)!", "hai @333!", ["Dr. (Budi)"]),
        # Only whole names: neither "@Analis" nor "@Anx" mentions An.
        ("@Analis", "@Analis", []),
        ("email@Anx", "email@Anx", []),
    ],
)
def test_mentions_use_whole_names_only(written, sent, used):
    assert mention(written) == {"text": sent, "used": used}
