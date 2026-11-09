import base64
import json
import sys
import threading

import pytest
from fakeBrowser import FakeBrowser
from whatsAppAccess import cdp, whatsApp

# The page already has this version's bridge.
CURRENT_BRIDGE = "!!(window.__waAccess && window.__waAccess.sourceHash === "
LINKED = {
    CURRENT_BRIDGE: True,
    "window.__waAccess.authState()": {"socket": "CONNECTED", "needsLink": False, "ready": True},
}
CHATS = [{"id": "1@c.us", "title": "Budi", "isGroup": False, "unread": 2}]
WHATSAPP_TABS = [
    {"type": "page", "url": "https://web.whatsapp.com/", "targetId": "T1"},
    {"type": "page", "url": "https://example.com/", "targetId": "T2"},
]


def page(expressions: dict, targets=None):
    """A browser with one WhatsApp tab. expressions maps the start of an expression to its value or error."""
    targets = WHATSAPP_TABS if targets is None else targets

    def handler(message):
        method = message["method"]
        if method == "Target.getTargets":
            return {"targetInfos": targets}
        if method == "Target.attachToTarget":
            assert message["params"] == {"targetId": "T1", "flatten": True}
            return {"sessionId": "S1"}
        if method == "Runtime.evaluate":
            expression = message["params"]["expression"]
            for start, value in expressions.items():
                if expression.startswith(start):
                    if isinstance(value, Exception):
                        description = str(value) + "\n    at x (y.js:1:2)"
                        return {
                            "result": {"type": "object"},
                            "exceptionDetails": {"exception": {"description": description}},
                        }
                    return {"result": {"type": "object", "value": value}}
            return {"result": {"type": "undefined"}}
        return {}

    return FakeBrowser(handler)


def session_for(browser, **kwargs):
    target = cdp.DebuggableBrowser(
        cdp.Browser("Brave", None, "brave.exe", ""), browser.port, "/devtools/browser/x"
    )
    session = whatsApp.WhatsAppSession(findBrowsers=lambda: [target], **kwargs)
    session.connect(target)
    return session


def test_connect_attaches_to_the_whatsapp_tab_and_installs_the_bridge():
    browser = page({"window.__waAccess.install()": True, **LINKED})
    session = session_for(browser)
    assert session.connected
    assert session.browserName == "Brave"
    methods = [m["method"] for m in browser.received]
    assert methods[:4] == [
        "Target.getTargets",
        "Target.attachToTarget",
        "Runtime.addBinding",
        "Runtime.enable",
    ]
    expressions = [m["params"]["expression"] for m in browser.received if m["method"] == "Runtime.evaluate"]
    assert expressions[0].startswith(CURRENT_BRIDGE)
    session.close()


def test_the_bridge_is_installed_when_the_page_has_none():
    browser = page(
        {
            "window.__waAccess.authState()": {"socket": "CONNECTED", "needsLink": False, "ready": True},
            "window.__waAccess.install()": True,
        }
    )
    session = session_for(browser)
    expressions = [m["params"]["expression"] for m in browser.received if m["method"] == "Runtime.evaluate"]
    assert any("window.__waAccess = {" in e for e in expressions)
    session.close()


def test_a_bridge_from_another_version_is_replaced():
    browser = page(
        {
            CURRENT_BRIDGE: False,
            "window.__waAccess.authState()": {"socket": "CONNECTED", "needsLink": False, "ready": True},
            "window.__waAccess.install()": True,
        }
    )
    session = session_for(browser)
    expressions = [m["params"]["expression"] for m in browser.received if m["method"] == "Runtime.evaluate"]
    source = next(i for i, e in enumerate(expressions) if "window.__waAccess = {" in e)
    # The new copy unhooks the old one itself, then is marked as this version's.
    assert "old.unhook()" in expressions[source]
    assert expressions[source + 1].startswith("window.__waAccess.sourceHash = ")
    session.close()


def test_a_failed_install_leaves_nothing_connected():
    lost = threading.Event()
    browser = page(
        {
            **LINKED,
            "window.__waAccess.install()": Exception("Error: Requiring unknown module 'WAWebMsgModel'"),
        }
    )
    target = cdp.DebuggableBrowser(
        cdp.Browser("Brave", None, "brave.exe", ""), browser.port, "/devtools/browser/x"
    )
    session = whatsApp.WhatsAppSession(findBrowsers=lambda: [target], onDisconnect=lost.set)
    with pytest.raises(whatsApp.WhatsAppError):
        session.connect(target)
    assert not session.connected
    # Not a lost connection: the caller reports the failure, and may simply try again.
    assert not lost.wait(0.5)


def test_features_whatsapp_took_away_are_kept_for_the_add_on_to_report():
    browser = page(
        {
            "window.__waAccess.install()": True,
            **LINKED,
            "window.__waAccess.missingFeatures()": ["reactions: WAWebCollections.Reactions is missing"],
        }
    )
    session = session_for(browser)
    assert session.missingFeatures == ["reactions: WAWebCollections.Reactions is missing"]
    session.close()


def test_a_call_is_tried_again_only_when_the_page_lost_the_bridge():
    sends = []

    def handler(message):
        method = message["method"]
        if method == "Target.getTargets":
            return {"targetInfos": WHATSAPP_TABS}
        if method == "Target.attachToTarget":
            return {"sessionId": "S1"}
        if method != "Runtime.evaluate":
            return {}
        expression = message["params"]["expression"]
        value = None
        if expression.startswith("window.__waAccess.sendText("):
            sends.append(expression)
            if len(sends) == 1:
                # The page reloaded: there is no bridge, so the function never ran.
                description = "TypeError: Cannot read properties of undefined (reading 'sendText')"
                return {
                    "result": {"type": "object"},
                    "exceptionDetails": {"exception": {"description": description}},
                }
            value = True
        elif expression.startswith('typeof window.__waAccess === "undefined"'):
            value = len(sends) == 1
        elif expression.startswith(CURRENT_BRIDGE) or expression.startswith("window.__waAccess.install()"):
            value = True
        elif expression.startswith("window.__waAccess.authState()"):
            value = LINKED["window.__waAccess.authState()"]
        return {"result": {"type": "object", "value": value}}

    session = session_for(FakeBrowser(handler))
    session.sendText("1@c.us", "halo")
    assert len(sends) == 2
    session.close()


def test_a_failed_send_is_not_sent_again_while_the_bridge_is_there():
    browser = page(
        {
            "window.__waAccess.install()": True,
            **LINKED,
            "window.__waAccess.sendText(": Exception("TypeError: x is not a function"),
            'typeof window.__waAccess === "undefined"': False,
        }
    )
    session = session_for(browser)
    with pytest.raises(whatsApp.WhatsAppError):
        session.sendText("1@c.us", "halo")
    sends = [
        m
        for m in browser.received
        if m["method"] == "Runtime.evaluate"
        and m["params"]["expression"].startswith("window.__waAccess.sendText(")
    ]
    assert len(sends) == 1
    session.close()


def test_no_whatsapp_tab():
    browser = page({}, targets=[WHATSAPP_TABS[1]])
    with pytest.raises(whatsApp.WhatsAppError) as error:
        session_for(browser)
    assert error.value.code == "noWhatsAppTab"


def test_refused_connection():
    browser = FakeBrowser(refuse=True)
    with pytest.raises(whatsApp.WhatsAppError) as error:
        session_for(browser)
    assert error.value.code == "refused"


def test_calls_pass_arguments_as_json_and_return_values():
    browser = page({"window.__waAccess.install()": True, **LINKED, "window.__waAccess.chats(": CHATS})
    session = session_for(browser)
    assert session.chats() == CHATS
    text = 'Halo "kamu"\nbaris dua'
    session.sendText("1@c.us", text)
    expression = browser.received[-1]["params"]["expression"]
    assert expression == f'window.__waAccess.sendText({json.dumps("1@c.us")}, {json.dumps(text)}, "", [])'
    assert browser.received[-1]["sessionId"] == "S1"
    session.sendText("1@c.us", "setuju", "false_1@c.us_ABC")
    expression = browser.received[-1]["params"]["expression"]
    assert expression == 'window.__waAccess.sendText("1@c.us", "setuju", "false_1@c.us_ABC", [])'
    session.chatAction("1@c.us", "mute", -1)
    expression = browser.received[-1]["params"]["expression"]
    assert expression == 'window.__waAccess.chatAction("1@c.us", "mute", -1)'
    session.close()


@pytest.mark.parametrize(
    ("thrown", "code", "detail"),
    [
        ("Error: chatNotFound", "chatNotFound", ""),
        ("Error: microphone:NotAllowedError", "microphone", "NotAllowedError"),
        ("Error: sendFailed:ERROR_UNKNOWN", "sendFailed", "ERROR_UNKNOWN"),
        ("TypeError: Cannot read properties of undefined", "failed", "TypeError: Cannot read"),
    ],
)
def test_page_errors_become_codes(thrown, code, detail):
    browser = page(
        {"window.__waAccess.install()": True, **LINKED, "window.__waAccess.sendText(": Exception(thrown)}
    )
    session = session_for(browser)
    with pytest.raises(whatsApp.WhatsAppError) as error:
        session.sendText("1@c.us", "x")
    assert error.value.code == code
    assert error.value.detail.startswith(detail)
    session.close()


def test_events_from_the_page_reach_the_listener():
    events = []
    received = threading.Event()

    def onEvent(event):
        events.append(event)
        received.set()

    browser = page({"window.__waAccess.install()": True, **LINKED})
    session = session_for(browser, onEvent=onEvent)
    payload = {"type": "message", "message": {"id": "m1", "text": "halo"}, "chat": {"id": "1@c.us"}}
    browser.send(
        {
            "method": "Runtime.bindingCalled",
            "params": {"name": whatsApp.EVENT_BINDING, "payload": json.dumps(payload)},
            "sessionId": "S1",
        }
    )
    assert received.wait(5)
    assert events == [payload]
    session.close()


def test_losing_the_browser_is_reported():
    lost = threading.Event()
    browser = page({"window.__waAccess.install()": True, **LINKED})
    session = session_for(browser, onDisconnect=lost.set)
    browser.disconnect()
    assert lost.wait(5)
    assert not session.connected
    with pytest.raises(whatsApp.WhatsAppError) as error:
        session.chats()
    assert error.value.code == "disconnected"


def test_closing_on_purpose_is_not_reported():
    lost = threading.Event()
    browser = page({"window.__waAccess.install()": True, **LINKED})
    session = session_for(browser, onDisconnect=lost.set)
    session.close()
    assert not lost.wait(0.5)


def downloading(name: str, content: bytes = b"hello", chunk=None):
    """A linked page with one file to download, named by its sender."""
    return page(
        {
            "window.__waAccess.install()": True,
            **LINKED,
            "window.__waAccess.downloadStart(": {"id": "D1", "name": name, "size": len(content)},
            "window.__waAccess.downloadChunk(": (
                chunk if chunk is not None else base64.b64encode(content).decode("ascii")
            ),
            "window.__waAccess.downloadEnd(": True,
        }
    )


def test_a_download_is_saved_under_a_safe_name(tmp_path):
    session = session_for(downloading("..\\..\\lapor:an.pdf"))
    path = session.download("M1", folder=str(tmp_path))
    assert path == str(tmp_path / "lapor_an.pdf")
    assert (tmp_path / "lapor_an.pdf").read_bytes() == b"hello"


def test_a_download_never_replaces_a_file(tmp_path):
    (tmp_path / "foto.jpg").write_bytes(b"mine")
    (tmp_path / "foto (2).jpg").write_bytes(b"mine")
    session = session_for(downloading("foto.jpg"))
    assert session.download("M1", folder=str(tmp_path)) == str(tmp_path / "foto (3).jpg")
    assert (tmp_path / "foto.jpg").read_bytes() == b"mine"


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS alternate data streams")
def test_a_download_is_marked_as_from_the_internet(tmp_path):
    session = session_for(downloading("tagihan.pdf"))
    path = session.download("M1", folder=str(tmp_path))
    with open(path + ":Zone.Identifier", encoding="ascii") as stream:
        assert "ZoneId=3" in stream.read()


def test_a_failed_download_leaves_no_partial_file(tmp_path):
    session = session_for(downloading("rusak.pdf", chunk=whatsApp.WhatsAppError("mediaGone")))
    with pytest.raises(whatsApp.WhatsAppError):
        session.download("M1", folder=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_a_download_the_page_cannot_start_is_reported(tmp_path):
    browser = page({"window.__waAccess.install()": True, **LINKED, "window.__waAccess.downloadStart(": None})
    session = session_for(browser)
    with pytest.raises(whatsApp.WhatsAppError) as raised:
        session.download("M1", folder=str(tmp_path))
    assert raised.value.code == "noDownload"


def test_a_whatsapp_waiting_to_be_linked_says_so():
    browser = page(
        {
            "!!(window.__waAccess && window.__waAccess.authState)": True,
            "window.__waAccess.authState()": {"socket": "UNPAIRED", "needsLink": True, "ready": False},
        }
    )
    target = cdp.DebuggableBrowser(
        cdp.Browser("Brave", None, "brave.exe", ""), browser.port, "/devtools/browser/x"
    )
    session = whatsApp.WhatsAppSession(findBrowsers=lambda: [target])
    assert session.connect(target) == "needsLink"
    assert not session.linked
    session.close()


def test_the_hidden_browser_gets_chromes_user_agent_before_whatsapp_opens():
    browser = page(
        {"window.__waAccess.install()": True, **LINKED},
        targets=[{"type": "page", "url": "about:blank", "targetId": "T1"}],
    )
    target = cdp.DebuggableBrowser(
        cdp.Browser("Brave", None, "brave.exe", ""), browser.port, "/devtools/browser/x"
    )
    session = whatsApp.WhatsAppSession(findBrowsers=lambda: [target])
    hidden = whatsApp.HiddenOptions(
        "Mozilla/5.0 Chrome/157.0.0.0", {"brands": []}, "https://web.whatsapp.com/"
    )
    assert session.connect(target, hidden) == "ready"
    methods = [m["method"] for m in browser.received]
    override = methods.index("Network.setUserAgentOverride")
    assert override < methods.index("Page.navigate")
    assert browser.received[override]["params"]["userAgent"] == "Mozilla/5.0 Chrome/157.0.0.0"
    session.close()


def test_memory_is_given_back_when_a_call_ends():
    received = threading.Event()
    browser = page({"window.__waAccess.install()": True, **LINKED})
    original = browser.handler

    def handler(message):
        if message["method"] == "HeapProfiler.collectGarbage":
            received.set()
        return original(message)

    browser.handler = handler
    session = session_for(browser)

    def call(state):
        payload = {"type": "call", "call": state}
        browser.send(
            {
                "method": "Runtime.bindingCalled",
                "params": {"name": whatsApp.EVENT_BINDING, "payload": json.dumps(payload)},
                "sessionId": "S1",
            }
        )

    call({"state": "connected", "isGroup": True})
    call(None)
    assert received.wait(5)
    methods = [m["method"] for m in browser.received]
    assert methods.index("Memory.simulatePressureNotification") < methods.index("HeapProfiler.collectGarbage")
    session.close()
