"""A fake browser DevTools endpoint: a WebSocket server on 127.0.0.1 that answers CDP commands from a script."""

import base64
import hashlib
import json
import socket
import struct
import threading

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _frame(opcode: int, payload: bytes) -> bytes:
    header = bytearray([0x80 | opcode])
    if len(payload) < 126:
        header.append(len(payload))
    elif len(payload) < 2**16:
        header.append(126)
        header += struct.pack(">H", len(payload))
    else:
        header.append(127)
        header += struct.pack(">Q", len(payload))
    return bytes(header) + payload


class FakeBrowser:
    """handler(message) returns the answer's result dict, or raises KeyError to answer with an error."""

    def __init__(self, handler=None, refuse: bool = False) -> None:
        self.handler = handler or (lambda message: {})
        self.refuse = refuse
        self.received: list[dict] = []
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.client: socket.socket | None = None
        self._sendLock = threading.Lock()
        threading.Thread(target=self._serve, daemon=True).start()

    def _recvExactly(self, count: int) -> bytes:
        data = b""
        while len(data) < count:
            chunk = self.client.recv(count - len(data))
            if not chunk:
                raise ConnectionError
            data += chunk
        return data

    def _serve(self) -> None:
        self.client, _ = self.server.accept()
        request = b""
        while b"\r\n\r\n" not in request:
            request += self.client.recv(4096)
        if self.refuse:
            self.client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            self.client.close()
            return
        key = next(
            line.split(":", 1)[1].strip()
            for line in request.decode().split("\r\n")
            if line.lower().startswith("sec-websocket-key")
        )
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        self.client.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode()
        )
        try:
            while True:
                first, second = self._recvExactly(2)
                length = second & 0x7F
                if length == 126:
                    (length,) = struct.unpack(">H", self._recvExactly(2))
                elif length == 127:
                    (length,) = struct.unpack(">Q", self._recvExactly(8))
                mask = self._recvExactly(4)
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._recvExactly(length)))
                opcode = first & 0x0F
                if opcode == 0x8:
                    self.client.close()
                    return
                if opcode != 0x1:
                    continue
                try:
                    message = json.loads(payload)
                except ValueError:
                    continue
                self.received.append(message)
                try:
                    answer = {"id": message["id"], "result": self.handler(message)}
                except KeyError as e:
                    answer = {"id": message["id"], "error": {"code": -32000, "message": str(e)}}
                if message.get("sessionId"):
                    answer["sessionId"] = message["sessionId"]
                self.send(answer)
        except (ConnectionError, OSError):
            return

    def send(self, message: dict) -> None:
        with self._sendLock:
            self.client.sendall(_frame(0x1, json.dumps(message).encode()))

    def ping(self) -> None:
        with self._sendLock:
            self.client.sendall(_frame(0x9, b"hi"))

    def disconnect(self) -> None:
        self.client.close()
