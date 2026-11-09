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


MEDIA_HELPER = r"""
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("\t// The HKDF \"info\" WhatsApp uses");
const end = source.indexOf("\t// Downloads a message's file for the add-on to save");
const [mode] = JSON.parse(process.argv[2]);

(async () => {
    const plain = new TextEncoder().encode("a voice note, more or less");
    const mediaKey = crypto.getRandomValues(new Uint8Array(32));
    const base = await crypto.subtle.importKey("raw", mediaKey, "HKDF", false, ["deriveBits"]);
    const expanded = new Uint8Array(await crypto.subtle.deriveBits(
        { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32), info: new TextEncoder().encode("WhatsApp Audio Keys") },
        base, 112 * 8));
    const iv = expanded.slice(0, 16);
    const aes = await crypto.subtle.importKey("raw", expanded.slice(16, 48), "AES-CBC", false, ["encrypt"]);
    const enc = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-CBC", iv }, aes, plain));
    const hmacKey = await crypto.subtle.importKey("raw", expanded.slice(48, 80), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const mac = new Uint8Array(await crypto.subtle.sign("HMAC", hmacKey, new Uint8Array([...iv, ...enc]))).slice(0, 10);
    const file = new Uint8Array([...enc, ...mac]);
    if (mode === "damaged") file[3] ^= 1;
    let fetched = null;
    let sent = 0;
    globalThis.fetch = async (url) => {
        fetched = url;
        if (mode === "saysHuge") {
            return new Response(file, { headers: { "content-length": String(10 ** 9) } });
        }
        if (mode === "endless") {
            // No length given, and more bytes than any limit: reading must stop by itself.
            const chunk = new Uint8Array(64 * 1024);
            return new Response(new ReadableStream({
                pull(controller) {
                    sent += chunk.length;
                    controller.enqueue(chunk);
                },
            }));
        }
        return new Response(file);
    };
    const downloadMedia = new Function(source.slice(start, end) + "; return downloadMedia;")();
    const m = {
        type: "ptt",
        mimetype: "audio/ogg; codecs=opus",
        mediaKey: Buffer.from(mediaKey).toString("base64"),
        directPath: mode === "elsewhere" ? "//evil.example/x" : "/v/t62.7117-24/abc?ccb=11",
    };
    try {
        const blob = await downloadMedia(m, mode === "small" ? 4 : 1024 * 1024);
        process.stdout.write(JSON.stringify({ ok: true, text: await blob.text(), fetched }));
    } catch (e) {
        const readTooMuch = sent > 2 * 1024 * 1024;
        process.stdout.write(JSON.stringify({ ok: false, error: e.message, fetched, readTooMuch }));
    }
})();
"""


def media(mode: str) -> dict:
    result = subprocess.run(
        [NODE, "-e", MEDIA_HELPER, str(PACKAGE_DIR / "pageBridge.js"), json.dumps([mode])],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def test_media_is_checked_then_decrypted():
    result = media("good")
    assert result == {
        "ok": True,
        "text": "a voice note, more or less",
        "fetched": "https://mmg.whatsapp.net/v/t62.7117-24/abc?ccb=11",
    }


def test_damaged_media_is_refused():
    assert media("damaged") == {
        "ok": False,
        "error": "mediaGone:damaged",
        "fetched": "https://mmg.whatsapp.net/v/t62.7117-24/abc?ccb=11",
        "readTooMuch": False,
    }


def test_media_from_another_host_is_not_fetched():
    result = media("elsewhere")
    assert result["ok"] is False
    assert result["fetched"] is None


@pytest.mark.parametrize("mode", ["saysHuge", "endless", "small"])
def test_media_larger_than_the_limit_is_not_read(mode):
    # Whatever size the message claims, the download stops at the limit.
    result = media(mode)
    assert result["ok"] is False
    assert result["error"] == "mediaGone:tooLarge"
    assert result["readTooMuch"] is False
