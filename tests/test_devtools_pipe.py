"""DevTools over a pipe: the framing, a connection over it, and the add-on's own browser for real."""

import json
import os
import shutil
import subprocess
import sys
import threading
import time

import pytest
from whatsAppAccess import browserLauncher, cdp


def pipePair():
    """Our transport, and the far end as the browser would hold it: (its read fd, its write fd)."""
    toFarRead, toFarWrite = os.pipe()
    fromFarRead, fromFarWrite = os.pipe()
    return cdp.PipeTransport(fromFarRead, toFarWrite), (toFarRead, fromFarWrite)


def test_messages_end_with_a_nul_byte():
    transport, (farRead, farWrite) = pipePair()
    transport.send('{"id":1}')
    assert os.read(farRead, 100) == b'{"id":1}\0'
    # Two messages in one write, and one message in two writes.
    os.write(farWrite, b'{"a":1}\0{"b":')
    os.write(farWrite, b"2}\0")
    assert transport.receive() == '{"a":1}'
    assert transport.receive() == '{"b":2}'
    transport.close()
    transport.closeReader()
    os.close(farRead)
    os.close(farWrite)


def test_the_browser_closing_its_end_ends_the_transport():
    transport, (farRead, farWrite) = pipePair()
    os.close(farWrite)
    with pytest.raises(cdp.WebSocketError):
        transport.receive()
    assert transport.closed
    with pytest.raises(cdp.WebSocketError):
        transport.send("{}")
    transport.closeReader()
    os.close(farRead)


def test_a_connection_over_a_pipe():
    transport, (farRead, farWrite) = pipePair()

    def farBrowser():
        buffer = b""
        while True:
            chunk = os.read(farRead, 65536)
            if not chunk:
                break
            buffer += chunk
            while b"\0" in buffer:
                message, _, buffer = buffer.partition(b"\0")
                request = json.loads(message)
                answer = {"id": request["id"], "result": {"method": request["method"]}}
                os.write(farWrite, json.dumps(answer).encode() + b"\0")
        # Our end closed: the browser exits, which closes its end too.
        os.close(farWrite)
        os.close(farRead)

    thread = threading.Thread(target=farBrowser, daemon=True)
    thread.start()
    closed = threading.Event()
    target = cdp.PipeBrowser(cdp.Browser("Fake", None, "fake.exe", ""), transport)
    connection = cdp.CdpConnection.open(target, onClose=closed.set)
    assert connection.call("Browser.getVersion") == {"method": "Browser.getVersion"}
    connection.close()
    assert closed.wait(5)
    thread.join(5)
    assert not thread.is_alive()
    # A pipe serves one connection only.
    with pytest.raises(cdp.Disconnected):
        cdp.CdpConnection.open(target)


def _listeningPorts(pid: int) -> list[str]:
    output = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, check=True
    ).stdout
    return [line for line in output.splitlines() if "LISTENING" in line and line.split()[-1] == str(pid)]


INSTALLED = browserLauncher.chooseBrowser(browserLauncher.findBrowsers()) if sys.platform == "win32" else None


@pytest.mark.skipif(INSTALLED is None, reason="No Chromium browser, version 120 or newer, is installed")
def test_the_hidden_browser_answers_on_its_pipe_and_opens_no_port(tmp_path):
    hidden = browserLauncher.HiddenBrowser(INSTALLED, str(tmp_path / "profile"))
    try:
        target = hidden.start()
        assert isinstance(target, cdp.PipeBrowser)
        connection = cdp.CdpConnection.open(target)
        version = connection.call("Browser.getVersion")
        assert version["product"]
        assert _listeningPorts(hidden.process.pid) == []
        process = hidden.process
        # Closing the add-on's end is enough: the browser exits by itself.
        connection.close()
        process.wait(timeout=20)
        # The next start finds the pipe closed and starts a new browser.
        again = hidden.start()
        assert again.transport is not target.transport
        assert hidden.running
    finally:
        hidden.stop()
        time.sleep(0.5)
        shutil.rmtree(tmp_path / "profile", ignore_errors=True)
