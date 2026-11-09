import threading
import time

import pytest
from fakeBrowser import FakeBrowser
from whatsAppAccess import cdp


def test_read_active_port(tmp_path):
    path = tmp_path / "DevToolsActivePort"
    path.write_text("9222\n/devtools/browser/5eec-f0e5\n")
    assert cdp.readActivePort(path) == (9222, "/devtools/browser/5eec-f0e5")


@pytest.mark.parametrize(
    "text", ["", "9222\n", "abc\n/devtools/browser/x\n", "9222\n/other\n", "70000\n/devtools/browser/x\n"]
)
def test_unusable_active_port_files_are_ignored(tmp_path, text):
    path = tmp_path / "DevToolsActivePort"
    path.write_text(text)
    assert cdp.readActivePort(path) is None


def test_missing_active_port_file(tmp_path):
    assert cdp.readActivePort(tmp_path / "missing") is None


def _browser(tmp_path, name, port):
    folder = tmp_path / name
    folder.mkdir()
    (folder / "DevToolsActivePort").write_text(f"{port}\n/devtools/browser/{name}\n")
    return cdp.Browser(name, folder, f"{name}.exe", "")


def test_only_browsers_that_own_their_port_are_found(tmp_path):
    brave = _browser(tmp_path, "brave", 9222)
    impostor = _browser(tmp_path, "chrome", 9333)
    found = cdp.findDebuggableBrowsers([brave, impostor], ownerCheck=lambda port, exe: port == 9222)
    assert [f.browser.name for f in found] == ["brave"]
    assert found[0].port == 9222


def test_most_recent_browser_comes_first(tmp_path):
    older = _browser(tmp_path, "older", 1111)
    time.sleep(0.05)
    newer = _browser(tmp_path, "newer", 2222)
    found = cdp.findDebuggableBrowsers([older, newer], ownerCheck=lambda port, exe: True)
    assert [f.browser.name for f in found] == ["newer", "older"]


def _connect(browser, **kwargs):
    target = cdp.DebuggableBrowser(
        cdp.Browser("Fake", None, "fake.exe", ""), browser.port, "/devtools/browser/x"
    )
    return cdp.CdpConnection.open(target, **kwargs)


def test_call_returns_the_result():
    browser = FakeBrowser(lambda message: {"method": message["method"]})
    connection = _connect(browser)
    assert connection.call("Target.getTargets") == {"method": "Target.getTargets"}
    assert connection.call("Runtime.evaluate", {"expression": "1"}, sessionId="S1") == {
        "method": "Runtime.evaluate"
    }
    assert browser.received[1]["sessionId"] == "S1"
    connection.close()


def test_errors_from_the_browser_are_raised():
    def handler(message):
        raise KeyError("No target with given id found")

    connection = _connect(FakeBrowser(handler))
    with pytest.raises(cdp.CdpError, match="No target"):
        connection.call("Target.attachToTarget")
    connection.close()


def test_events_reach_the_listener():
    events = []
    received = threading.Event()

    def onEvent(method, params, sessionId):
        events.append((method, params, sessionId))
        received.set()

    browser = FakeBrowser()
    connection = _connect(browser, onEvent=onEvent)
    connection.call("Runtime.enable")
    browser.send(
        {"method": "Runtime.bindingCalled", "params": {"name": "x", "payload": "{}"}, "sessionId": "S"}
    )
    assert received.wait(5)
    assert events == [("Runtime.bindingCalled", {"name": "x", "payload": "{}"}, "S")]
    connection.close()


def test_a_lost_connection_ends_waiting_calls_and_is_reported():
    closed = threading.Event()
    browser = FakeBrowser(lambda message: time.sleep(10) or {})
    connection = _connect(browser, onClose=closed.set)
    threading.Timer(0.2, browser.disconnect).start()
    with pytest.raises(cdp.Disconnected):
        connection.call("Slow.method", timeout=5)
    assert closed.wait(5)
    with pytest.raises(cdp.Disconnected):
        connection.call("Another.method")


@pytest.mark.parametrize(
    "url",
    ["https://web.whatsapp.com/", "https://web.whatsapp.com", "https://WEB.whatsapp.com:443/send?x=1"],
)
def test_whatsapp_web_is_recognised(url):
    assert cdp.isWhatsAppUrl(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://web.whatsapp.com.evil.example/",
        "https://web.whatsapp.com@evil.example/",
        "https://evil.example/https://web.whatsapp.com",
        "http://web.whatsapp.com/",
        "https://web.whatsapp.com:8443/",
        "https://web.whatsapp.com:bad/",
        "https://x.web.whatsapp.com/",
        "",
    ],
)
def test_look_alike_addresses_are_not_whatsapp(url):
    assert not cdp.isWhatsAppUrl(url)


def test_only_whatsapps_exact_origin_counts():
    assert cdp.isWhatsAppOrigin("https://web.whatsapp.com")
    assert not cdp.isWhatsAppOrigin("https://web.whatsapp.com.evil.example")
    assert not cdp.isWhatsAppOrigin("https://web.whatsapp.com:8443")
    assert not cdp.isWhatsAppOrigin("")
