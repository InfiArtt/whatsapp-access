# WhatsApp Access add-on
# Copyright (C) 2026 InfiArtt
# This file is covered by the GNU General Public License.

"""A small WebSocket client (RFC 6455), enough to talk to a browser's DevTools endpoint on this computer.

NVDA ships no WebSocket library, and this add-on needs only text messages over a loopback connection.
It imports nothing from NVDA, so it can be tested on its own.
"""

import base64
import hashlib
import os
import socket
import struct
import threading

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA
MAX_MESSAGE_BYTES = 64 * 2**20


class WebSocketError(Exception):
	"""The connection failed or was closed."""


class HandshakeRefused(WebSocketError):
	"""The server answered the upgrade request with something other than 101, for example 403."""

	def __init__(self, status: str) -> None:
		super().__init__(f"WebSocket handshake refused: {status}")
		self.status = status


def acceptKey(key: str) -> str:
	return base64.b64encode(hashlib.sha1((key + _GUID).encode("ascii")).digest()).decode("ascii")


def encodeFrame(opcode: int, payload: bytes, mask: bytes | None = None) -> bytes:
	"""One final frame. Clients must mask what they send; tests pass a fixed mask."""
	if mask is None:
		mask = os.urandom(4)
	header = bytearray([0x80 | opcode])
	length = len(payload)
	if length < 126:
		header.append(0x80 | length)
	elif length < 2**16:
		header.append(0x80 | 126)
		header += struct.pack(">H", length)
	else:
		header.append(0x80 | 127)
		header += struct.pack(">Q", length)
	header += mask
	masked = (
		bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		if len(payload) < 4096
		else _maskFast(payload, mask)
	)
	return bytes(header) + masked


def _maskFast(payload: bytes, mask: bytes) -> bytes:
	repeated = (mask * (len(payload) // 4 + 1))[: len(payload)]
	return (int.from_bytes(payload, "big") ^ int.from_bytes(repeated, "big")).to_bytes(len(payload), "big")


class WebSocket:
	"""A connected client. send() may be called from any thread; receive() from one reader thread."""

	def __init__(self, sock: socket.socket) -> None:
		self._sock = sock
		self._sendLock = threading.Lock()
		self._buffer = b""
		self.closed = False

	@classmethod
	def connect(cls, host: str, port: int, path: str, handshakeTimeout: float) -> "WebSocket":
		"""Connect and upgrade. The browser may hold the answer until the user allows remote debugging."""
		sock = socket.create_connection((host, port), timeout=10)
		try:
			key = base64.b64encode(os.urandom(16)).decode("ascii")
			request = (
				f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
				f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
			)
			sock.sendall(request.encode("ascii"))
			sock.settimeout(handshakeTimeout)
			response = b""
			while b"\r\n\r\n" not in response:
				chunk = sock.recv(4096)
				if not chunk:
					raise WebSocketError("The browser closed the connection during the handshake")
				response += chunk
				if len(response) > 65536:
					raise WebSocketError("Handshake response too long")
			head, _, rest = response.partition(b"\r\n\r\n")
			lines = head.decode("latin-1").split("\r\n")
			status = lines[0]
			if " 101 " not in status + " ":
				raise HandshakeRefused(status)
			headers = {}
			for line in lines[1:]:
				name, _, value = line.partition(":")
				headers[name.strip().lower()] = value.strip()
			if headers.get("sec-websocket-accept") != acceptKey(key):
				raise WebSocketError("The server's handshake answer did not match")
			sock.settimeout(None)
		except BaseException:
			sock.close()
			raise
		ws = cls(sock)
		ws._buffer = rest
		return ws

	def _readExactly(self, count: int) -> bytes:
		while len(self._buffer) < count:
			chunk = self._sock.recv(max(65536, count - len(self._buffer)))
			if not chunk:
				raise WebSocketError("Connection closed")
			self._buffer += chunk
		data, self._buffer = self._buffer[:count], self._buffer[count:]
		return data

	def _readFrame(self) -> tuple[bool, int, bytes]:
		first, second = self._readExactly(2)
		fin, opcode = bool(first & 0x80), first & 0x0F
		length = second & 0x7F
		if length == 126:
			(length,) = struct.unpack(">H", self._readExactly(2))
		elif length == 127:
			(length,) = struct.unpack(">Q", self._readExactly(8))
		if length > MAX_MESSAGE_BYTES:
			raise WebSocketError("Message too large")
		mask = self._readExactly(4) if second & 0x80 else None
		payload = self._readExactly(length)
		if mask:
			payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		return fin, opcode, payload

	def receive(self) -> str:
		"""The next text message. Answers pings. Raises WebSocketError when the connection ends."""
		parts: list[bytes] = []
		while True:
			try:
				fin, opcode, payload = self._readFrame()
			except OSError as e:
				self.closed = True
				raise WebSocketError(str(e)) from e
			except WebSocketError:
				self.closed = True
				raise
			if opcode == OP_PING:
				self._send(OP_PONG, payload)
				continue
			if opcode == OP_PONG:
				continue
			if opcode == OP_CLOSE:
				self.closed = True
				try:
					self._send(OP_CLOSE, payload[:2])
				except OSError:
					pass
				raise WebSocketError("The browser closed the connection")
			if opcode in (OP_TEXT, OP_BINARY, OP_CONTINUATION):
				parts.append(payload)
				if sum(len(p) for p in parts) > MAX_MESSAGE_BYTES:
					raise WebSocketError("Message too large")
				if fin:
					return b"".join(parts).decode("utf-8", errors="replace")

	def _send(self, opcode: int, payload: bytes) -> None:
		with self._sendLock:
			self._sock.sendall(encodeFrame(opcode, payload))

	def send(self, text: str) -> None:
		if self.closed:
			raise WebSocketError("Connection closed")
		try:
			self._send(OP_TEXT, text.encode("utf-8"))
		except OSError as e:
			self.closed = True
			raise WebSocketError(str(e)) from e

	def close(self) -> None:
		if not self.closed:
			try:
				self._send(OP_CLOSE, struct.pack(">H", 1000))
			except OSError:
				pass
		self.closed = True
		try:
			self._sock.close()
		except OSError:
			pass
