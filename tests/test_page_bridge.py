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


NAMES_HELPER = r"""
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
// Each function from "\tfunction name(" to the tab and brace that close it.
const take = (name) => {
    const start = source.indexOf("\tfunction " + name + "(");
    return source.slice(start, source.indexOf("\n\t}\n", start) + 4);
};
const wid = (text) => {
    const [user, server] = text.split("@");
    return { user, server, toString: () => text };
};
const [contacts, phones, ask] = JSON.parse(process.argv[2]);
const Contact = { get: (id) => {
    const found = contacts[String(id)];
    return found ? Object.assign({ id: wid(String(id)) }, found) : undefined;
} };
const req = (module) => ({
    WAWebApiContact: { getPhoneNumber: (id) => (phones[String(id)] ? wid(phones[String(id)]) : null) },
    WAWebWidFactory: { createWid: wid },
})[module];
const collections = () => ({ Contact });
const code = "const VERIFIED_HIGH = 2;" +
    ["phoneWidOf", "contactOf", "personName", "contactName", "withMentionNames", "senderName"].map(take).join("\n") +
    "; return { contactName, withMentionNames, senderName };";
const f = new Function("req", "collections", code)(req, collections);
const out = {};
for (const [key, call] of Object.entries(ask)) {
    if (call.contactName) out[key] = f.contactName(call.contactName);
    if (call.mention) out[key] = f.withMentionNames({ mentionedJidList: call.mention[1].map(wid) }, call.mention[0]);
    if (call.sender) out[key] = f.senderName({ id: { fromMe: false }, author: call.sender[0] && wid(call.sender[0]), notifyName: call.sender[1] });
}
process.stdout.write(JSON.stringify(out));
"""

CONTACTS = {
    "111@c.us": {"name": "Mom", "pushname": "Siti"},
    "222@c.us": {"pushname": "Mom"},
    "333@c.us": {"verifiedName": "Bank BCA", "verifiedLevel": 2},
    "444@c.us": {"verifiedName": "Bank BCA", "verifiedLevel": 0},
    "900@lid": {"pushname": "Budi"},
    "62812@c.us": {"name": "Andi"},
    "901@lid": {},
}
PHONES = {"900@lid": "6281234567890@c.us", "901@lid": "62812@c.us"}


def names(ask: dict) -> dict:
    result = subprocess.run(
        [NODE, "-e", NAMES_HELPER, str(PACKAGE_DIR / "pageBridge.js"), json.dumps([CONTACTS, PHONES, ask])],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("wid", "name"),
    [
        # Saved contacts keep the name the user gave them.
        ("111@c.us", "Mom"),
        # Anyone else is their number, then "~" and the name they chose, as in WhatsApp.
        ("222@c.us", "+222 ~Mom"),
        ("900@lid", "+6281234567890 ~Budi"),
        # A name saved under the number counts for the newer id too.
        ("901@lid", "Andi"),
        # Only a business name WhatsApp has verified is shown as a name.
        ("333@c.us", "Bank BCA"),
        ("444@c.us", "+444 ~Bank BCA"),
        ("555@c.us", "+555"),
    ],
)
def test_names_people_choose_are_not_taken_for_saved_ones(wid, name):
    assert names({"x": {"contactName": wid}}) == {"x": name}


def test_group_senders_are_named_the_same_way():
    assert names(
        {
            "stranger": {"sender": ["777@c.us", "Bank"]},
            "saved": {"sender": ["111@c.us", "Ibu"]},
        }
    ) == {"stranger": "+777 ~Bank", "saved": "Mom"}


@pytest.mark.parametrize(
    ("text", "sent"),
    [
        ("halo @62812", "halo @Andi"),
        ("@62812, ok", "@Andi, ok"),
        # A longer number that starts with the same digits is someone else.
        ("@6281234567 dan @62812", "@6281234567 dan @Andi"),
    ],
)
def test_mentions_replace_whole_numbers_only(text, sent):
    assert names({"x": {"mention": [text, ["62812@c.us"]]}}) == {"x": sent}


RECORDING_HELPER = r"""
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("\tconst OPUS_RATES");
const end = source.indexOf("\tasync function sendRecording");
const log = [];
let track = null;
// A microphone that gives one 20 ms frame, then nothing until it is stopped.
const navigator = { mediaDevices: { getUserMedia: async () => {
    let wake = null;
    track = { label: "Test microphone", stopped: false, stop() {
        this.stopped = true;
        if (wake) wake();
    } };
    track.ended = new Promise((resolve) => { wake = resolve; });
    return { getAudioTracks: () => [track], getTracks: () => [track] };
} } };
class MediaStreamTrackProcessor {
    constructor({ track }) {
        let sent = false;
        this.readable = { getReader: () => ({ read: async () => {
            if (!sent) {
                sent = true;
                return { done: false, value: {
                    numberOfChannels: 1, sampleRate: 48000, numberOfFrames: 960,
                    copyTo() {}, close() {},
                } };
            }
            await track.ended;
            return { done: true };
        } }) };
    }
}
class AudioEncoder {
    constructor({ output }) { this.output = output; this.state = "unconfigured"; }
    configure() { this.state = "configured"; }
    encode() {
        this.output({ byteLength: 3, duration: 20000, copyTo(data) { data.set([1, 2, 3]); } }, null);
    }
    async flush() {}
    close() { this.state = "closed"; }
}
const timers = [];
const setTimeout = (callback, ms) => { timers.push({ callback, ms, cleared: false }); return timers.length - 1; };
const clearTimeout = (id) => { if (timers[id]) timers[id].cleared = true; };
const emit = (event) => log.push(event.type);
const code = "let ownMicrophoneRequest = false;" + source.slice(start, end) +
    "; return { startRecording, stopRecording, cancelRecording, isRecording: () => !!recording };";
const r = new Function("navigator", "MediaStreamTrackProcessor", "AudioEncoder", "setTimeout", "clearTimeout", "emit", code)(
    navigator, MediaStreamTrackProcessor, AudioEncoder, setTimeout, clearTimeout, emit);
const [mode] = JSON.parse(process.argv[2]);

(async () => {
    const out = {};
    await r.startRecording({});
    await new Promise((resolve) => globalThis.setTimeout(resolve, 10));
    out.limitMinutes = timers[0].ms / 60000;
    if (mode === "limit") {
        timers[0].callback();
        out.recordingAfterLimit = r.isRecording();
        out.microphoneOpen = !track.stopped;
        out.events = log;
        const result = await r.stopRecording();
        out.stopped = { duration: result.duration, channels: result.channels };
        out.again = await r.stopRecording().then(() => "ok", (e) => e.message);
    } else {
        await r.cancelRecording();
        out.microphoneOpen = !track.stopped;
        out.timerCleared = timers[0].cleared;
        out.stop = await r.stopRecording().then(() => "ok", (e) => e.message);
    }
    process.stdout.write(JSON.stringify(out));
})();
"""


def recording(mode: str) -> dict:
    result = subprocess.run(
        [NODE, "-e", RECORDING_HELPER, str(PACKAGE_DIR / "pageBridge.js"), json.dumps([mode])],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)


def test_recording_stops_by_itself_at_its_limit():
    # As if the user had stopped it: the microphone closes, and stopping it later gives the voice note.
    assert recording("limit") == {
        "limitMinutes": 30,
        "recordingAfterLimit": False,
        "microphoneOpen": False,
        "events": ["recordingLimit"],
        "stopped": {"duration": 0.02, "channels": 1},
        "again": "notRecording",
    }


def test_cancelled_recording_forgets_its_limit():
    assert recording("cancel") == {
        "limitMinutes": 30,
        "microphoneOpen": False,
        "timerCleared": True,
        "stop": "notRecording",
    }


CALL_AUDIO_HELPER = r"""
const fs = require("fs");
const source = fs.readFileSync(process.argv[1], "utf8");
const start = source.indexOf("\tfunction forgetClosedCallAudio(");
const body = source.slice(start, source.indexOf("\n\t}\n", start) + 4);
class MediaStream {
    constructor(active) { this.active = active; }
}
const callLoudness = {
    gains: new Set([{ name: "open", context: { state: "running" } }, { name: "ended", context: { state: "closed" } }]),
    media: new Set([
        { name: "playing", srcObject: new MediaStream(true) },
        { name: "finished", srcObject: new MediaStream(false) },
        { name: "emptied", srcObject: null },
    ]),
};
new Function("callLoudness", "MediaStream", body + "; forgetClosedCallAudio();")(callLoudness, MediaStream);
process.stdout.write(JSON.stringify({
    gains: [...callLoudness.gains].map((g) => g.name),
    media: [...callLoudness.media].map((m) => m.name),
}));
"""


def test_audio_of_ended_calls_is_forgotten():
    result = subprocess.run(
        [NODE, "-e", CALL_AUDIO_HELPER, str(PACKAGE_DIR / "pageBridge.js")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert json.loads(result.stdout) == {"gains": ["open"], "media": ["playing"]}
