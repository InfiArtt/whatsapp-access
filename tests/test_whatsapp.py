import json
import threading

import pytest
from fakeBrowser import FakeBrowser
from whatsAppAccess import cdp, whatsApp

LINKED = {
    "!!(window.__waAccess && window.__waAccess.authState)": True,
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
    assert expressions[0] == "!!(window.__waAccess && window.__waAccess.authState)"
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


def test_saved_files_get_names_windows_accepts(tmp_path):
    assert whatsApp._safeFileName('lapor:an?"1"/2.pdf') == "2.pdf"
    assert whatsApp._safeFileName("a<b>c|d*e.txt") == "a_b_c_d_e.txt"
    assert whatsApp._safeFileName("...") == "WhatsApp file"


def test_saving_never_overwrites(tmp_path):
    (tmp_path / "foto.jpg").write_bytes(b"x")
    (tmp_path / "foto (2).jpg").write_bytes(b"x")
    assert whatsApp._freePath(str(tmp_path), "foto.jpg") == str(tmp_path / "foto (3).jpg")
    assert whatsApp._freePath(str(tmp_path), "baru.jpg") == str(tmp_path / "baru.jpg")


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
