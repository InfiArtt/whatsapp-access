import json
import threading

import pytest
from fakeBrowser import FakeBrowser
from whatsAppAccess import webSocket


def test_accept_key_matches_rfc_example():
    assert webSocket.acceptKey("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


@pytest.mark.parametrize("size", [0, 5, 125, 126, 70000])
def test_frames_are_masked_and_carry_their_length(size):
    payload = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
    frame = webSocket.encodeFrame(webSocket.OP_TEXT, payload, mask=b"\x01\x02\x03\x04")
    assert frame[0] == 0x81
    assert frame[1] & 0x80
    offset = 2 if size < 126 else 4 if size < 2**16 else 10
    mask = frame[offset : offset + 4]
    body = frame[offset + 4 :]
    assert bytes(b ^ mask[i % 4] for i, b in enumerate(body)) == payload


def test_round_trip_with_a_server():
    browser = FakeBrowser(lambda message: {"echo": message["params"]})
    ws = webSocket.WebSocket.connect("127.0.0.1", browser.port, "/devtools/browser/x", 5)
    ws.send(json.dumps({"id": 1, "method": "Echo", "params": {"text": "halo"}}))
    assert json.loads(ws.receive()) == {"id": 1, "result": {"echo": {"text": "halo"}}}
    ws.close()


def test_pings_are_answered_and_skipped():
    browser = FakeBrowser()
    ws = webSocket.WebSocket.connect("127.0.0.1", browser.port, "/devtools/browser/x", 5)
    browser.ping()
    browser.send({"after": "ping"})
    assert json.loads(ws.receive()) == {"after": "ping"}
    ws.close()


def test_refused_handshake_is_reported():
    browser = FakeBrowser(refuse=True)
    with pytest.raises(webSocket.HandshakeRefused) as error:
        webSocket.WebSocket.connect("127.0.0.1", browser.port, "/devtools/browser/x", 5)
    assert "403" in error.value.status


def test_receive_raises_when_the_server_goes_away():
    browser = FakeBrowser()
    ws = webSocket.WebSocket.connect("127.0.0.1", browser.port, "/devtools/browser/x", 5)
    threading.Timer(0.1, browser.disconnect).start()
    with pytest.raises(webSocket.WebSocketError):
        ws.receive()
